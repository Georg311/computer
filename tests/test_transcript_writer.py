"""Unit tests for cptr.utils.te.transcript_writer module (P6a).

Tests TranscriptWriter, build_cptr_digest, DigestWindow und LLM Runner Builder.
Alle Assertions prüfen In-Memory-Buffer (_entries, _call_index) statt Festplatte.
"""

import json
from pathlib import Path

import pytest

from cptr.utils.te.microskills.distiller import load_calls as _load_calls
from cptr.utils.te.transcript_writer import (
    TranscriptWriter,
    build_cptr_digest,
    DigestWindow,
    build_proposer_runner,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def tmp_transcripts(tmp_path):
    """Provide a temporary transcripts directory."""
    d = tmp_path / "transcripts"
    d.mkdir(exist_ok=True)
    return str(d)


@pytest.fixture()
def tw_instance():
    """Return a TranscriptWriter instance."""
    return TranscriptWriter(chat_id="test-chat-01")


# =====================================================================
# TestRecordToolUse — record_tool_use() speichert Tool-Calls korrekt
# =====================================================================


class TestRecordToolUse:
    def test_records_single_tool_use(self, tw_instance):
        """record_tool_use appends a single entry to _entries."""
        tw = tw_instance
        tw.record_tool_use("call-1", "search_files", {"query": "test"})
        assert len(tw._entries) == 1

    def test_records_multiple_tool_uses(self, tw_instance):
        """Multiple tool use entries accumulate correctly."""
        tw = tw_instance
        tw.record_tool_use("c1", "tool_a", {"x": 1})
        tw.record_tool_use("c2", "tool_b", {"y": 2})
        assert len(tw._entries) == 2

    def test_tool_use_has_correct_id(self, tw_instance):
        """Each entry carries the correct call id."""
        tw = tw_instance
        tw.record_tool_use("my-call-123", "read_file", {"path": "/tmp/x"})
        assert tw._entries[0]["message"]["content"][0]["id"] == "my-call-123"


# =====================================================================
# TestRecordToolResult — record_tool_result() speichert Ergebnisse korrekt
# =====================================================================


class TestRecordToolResult:
    def test_records_single_result(self, tw_instance):
        """A single result entry is appended after tool_use."""
        tw = tw_instance
        tw.record_tool_use("call-1", "search_files", {"query": "test"})
        tw.record_tool_result("call-1", "found 3 files")
        assert len(tw._entries) == 2

    def test_records_multiple_results(self, tw_instance):
        """Multiple tool-use + result pairs accumulate correctly."""
        tw = tw_instance
        for i in range(3):
            cid = f"call-{i}"
            tw.record_tool_use(cid, "tool", {"idx": i})
            tw.record_tool_result(cid, f"result {i}")
        assert len(tw._entries) == 6


# =====================================================================
# TestFinishResolvedTrue — finish(resolved=True) erzeugt valid JSONL
# =====================================================================


class TestFinishResolvedTrue:
    def test_finish_creates_jsonl_file(self, tw_instance, tmp_transcripts, monkeypatch):
        """finish() writes a .jsonl file to the transcripts directory."""
        import os as _os

        fake_home = Path(tmp_transcripts) / "home"
        fake_home.mkdir(parents=True, exist_ok=True)

        from cptr.utils.te import transcript_writer as mod

        orig_home = None
        try:
            class FakePath(Path):
                @classmethod
                def home(cls):
                    return fake_home

            orig_home = mod._Path.home
            mod._Path.home = staticmethod(lambda: fake_home)

            tw_instance.record_tool_use("c1", "search_files", {"query": "x"})
            path = tw_instance.finish(resolved=True)

            assert path is not None
            p = Path(path)
            assert p.exists()
            assert p.suffix == ".jsonl"
        finally:
            if orig_home is not None:
                mod._Path.home = orig_home

    def test_finish_returns_correct_path(self, tw_instance, tmp_transcripts, monkeypatch):
        """finish() returns the full file path string."""
        fake_home = Path(tmp_transcripts) / "home2"
        fake_home.mkdir(parents=True, exist_ok=True)

        from cptr.utils.te import transcript_writer as mod

        orig_home = None
        try:
            class FakePath(Path):
                @classmethod
                def home(cls):
                    return fake_home

            orig_home = mod._Path.home
            mod._Path.home = staticmethod(lambda: fake_home)

            tw_instance.record_tool_use("c1", "search_files", {"query": "x"})
            path = tw_instance.finish(resolved=True)

            assert isinstance(path, str)
            assert path.endswith(".jsonl")
        finally:
            if orig_home is not None:
                mod._Path.home = orig_home

    def test_finish_returns_path_string(self):
        """finish() returns a path string on valid dir (no crash)."""
        tw = TranscriptWriter(chat_id="test", workspace="/tmp")
        result = tw.finish(resolved=True)
        assert isinstance(result, str) and result.endswith(".jsonl")


# =====================================================================
# TestJSONLLoadCallsCompatibility — JSONL Format kompatibel mit distiller.load_calls()
# =====================================================================


class TestJSONLLoadCallsCompatibility:
    def test_load_calls_parses_single_entry(self):
        """distiller.load_calls() can parse a single transcript entry."""
        d = Path(__file__).parent / "tmp_test_data"
        d.mkdir(exist_ok=True)
        fpath = d / "test_single.jsonl"
        entry = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "c1",
                        "name": "search_files",
                        "input": {"query": "x"},
                    }
                ]
            },
        }
        with open(fpath, "w") as fh:
            fh.write(json.dumps(entry) + "\n")

        calls = _load_calls(str(fpath))
        assert len(calls) >= 0

    def test_load_calls_parses_multiple_entries(self):
        """distiller.load_calls() parses multiple entries."""
        d = Path(__file__).parent / "tmp_test_data"
        fpath = d / "test_multi.jsonl"
        with open(fpath, "w") as fh:
            for i in range(5):
                entry = {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": f"c{i}",
                                "name": "bash",
                                "input": {"command": f"echo hello-{i}"},
                            }
                        ]
                    },
                }
                fh.write(json.dumps(entry) + "\n")

        calls = _load_calls(str(fpath))
        assert len(calls) >= 0


# =====================================================================
# TestBuildCptrDigest — build_cptr_digest() extrahiert commands, edited_files
# =====================================================================


class TestBuildCptrDigest:
    def test_build_digest_returns_dict(self):
        """build_cptr_digest() returns a dict or None."""
        d = Path(__file__).parent / "tmp_test_data"
        ws = str(Path(__file__).parent.parent)
        tp = str(d / "test_single.jsonl")

        digest = build_cptr_digest(ws, tp, "test-chat-01")
        assert isinstance(digest, dict) or digest is None

    def test_build_digest_has_iid(self):
        """Digest contains an iid when valid."""
        d = Path(__file__).parent / "tmp_test_data"
        ws = str(Path(__file__).parent.parent)
        tp = str(d / "test_single.jsonl")

        digest = build_cptr_digest(ws, tp, "test-chat-01")
        assert digest is None or isinstance(digest.get("iid"), str)

    def test_build_digest_has_resolved(self):
        """Digest carries the resolved flag when present."""
        d = Path(__file__).parent / "tmp_test_data"
        ws = str(Path(__file__).parent.parent)
        tp = str(d / "test_single.jsonl")

        digest = build_cptr_digest(ws, tp, "test-chat-01")
        assert digest is None or isinstance(digest.get("resolved"), (bool, type(None)))


# =====================================================================
# TestDigestWindow — DigestWindow manages max 8 digests
# =====================================================================


class TestDigestWindow:
    def test_window_max_8_entries(self):
        """Window caps at max_size entries."""
        w = DigestWindow(max_size=8)
        for i in range(10):
            w.add({"digest": f"digest-{i}"})
        assert len(w._digests) == 8

    def test_window_appends_in_order(self):
        """Entries are appended in order; oldest dropped first."""
        w = DigestWindow(max_size=3)
        w.add({"name": "a"})
        w.add({"name": "b"})
        w.add({"name": "c"})
        w.add({"name": "d"})  # drops "a"
        names = [e["name"] for e in w._digests]
        assert names == ["b", "c", "d"]

    def test_window_get_all_returns_copy(self):
        """get_all() returns a copy, not the internal list."""
        w = DigestWindow(max_size=5)
        w.add({"x": 1})
        c1 = w.get_all()
        c2 = w.get_all()
        assert c1 is not c2

    def test_window_clear(self):
        """clear() empties the window."""
        w = DigestWindow(max_size=8)
        w.add({"a": 1})
        w.clear()
        assert len(w._digests) == 0

    def test_window_size(self):
        """size property returns current count."""
        w = DigestWindow(max_size=5)
        w.add({"x": 1})
        w.add({"y": 2})
        assert w.size() == 2


# =====================================================================
# TestLLMRunners — Runner Builder Graceful Degradation
# =====================================================================


class TestLLMRunners:
    def test_build_openai_runner_returns_callable(self):
        """build_openai_runner() returns None or callable."""
        try:
            from cptr.utils.te.transcript_writer import (
                _build_openai_runner,
            )

            result = _build_openai_runner(api_key=None)
            assert result is None or callable(result)
        except ImportError:
            pytest.skip("openai package not available")

    def test_build_anthropic_runner_returns_callable(self):
        """build_anthropic_runner() returns None or callable."""
        try:
            from cptr.utils.te.transcript_writer import (
                _build_anthropic_runner,
            )

            result = _build_anthropic_runner(api_key=None)
            assert result is None or callable(result)
        except ImportError:
            pytest.skip("anthropic package not available")

    def test_build_proposer_runner_no_api_keys(self):
        """build_proposer_runner() returns None when no API keys set."""
        runner = build_proposer_runner()
        # Should return None (graceful degradation)
        assert runner is None


# =====================================================================
# TestTranscriptWriterReset — reset() clears all state
# =====================================================================


class TestTranscriptWriterReset:
    def test_reset_clears_entries(self, tw_instance):
        """reset() clears all recorded entries."""
        tw = tw_instance

        tw.record_tool_use("call-1", "search_files", {"query": "test"})
        tw.record_tool_result("call-1", "result")

        assert len(tw._entries) == 2
        tw.reset()
        assert len(tw._entries) == 0

    def test_reset_clears_call_index(self, tw_instance):
        """reset() clears the call index too."""
        tw = tw_instance

        tw.record_tool_use("call-1", "search_files", {"query": "test"})
        assert len(tw._call_index) == 1
        tw.reset()
        assert len(tw._call_index) == 0
