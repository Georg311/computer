# Manifesto

> **TL;DR** We pushed code and went to dinner. Prod broke. Phone in pocket, laptop at home. The fix was on our computer, not in some fresh cloud box. So we built Open WebUI Computer: your actual machine, in any browser. Files, terminal, editor, git, running sessions, all of it. Phone, tablet, laptop, whatever. It literally is your computer. Now go outside.

Your computer is where your work lives.

Not in the abstract. Literally.

The repo you already cloned. The branch you forgot was still dirty. The terminal that is still running. The `.env` file you made three months ago and never want to recreate. The local database with the weird test state. The SSH key, the shell history, the editor tabs, the scripts that only work because your machine has slowly become your machine.

That is the computer you trust.

And yet the moment you step away from the desk, most tools ask you to leave it behind.

Open a cloud development environment. Start a new workspace. Wait for it to build. Reconnect accounts. Reinstall packages. Copy secrets. Recreate the thing you already had. It is useful. Sometimes it is exactly right. But it is not your computer. It is another place to work.

Most of the time, you do not want another place to work.

You want the place where the work already is.

## The Small Interruptions

The hard parts of work still deserve the desk. Big refactors. Deep debugging. Four panes of context. A real keyboard. A quiet hour.

But a lot of the day is not that.

A build finishes while you are making coffee. A deploy fails while you are on the couch. A customer reports a bug while you are on the train. An agent finishes a task while you are walking outside. You do not need to "go to work" for that. You need to look at the output, read the diff, check the logs, maybe type one sentence, maybe press the button.

The task takes thirty seconds.

The laptop turns it into a ritual.

Find the machine. Open the lid. Wait for the network. Unlock it. Find the window. Remember where you were. Sit down even though you were only trying to check whether CI passed.

The work was small. The interface made it large.

## The Desk

Nobody chose the desk forever. We inherited it.

The first computers filled rooms, so people went to the computer. Then computers became personal, but they were still furniture: tower, monitor, keyboard, mouse, cables, power. The desk made sense because the machine lived there.

Laptops made the desk portable, but they did not change the basic deal. You still open the computer, face the screen, put both hands on the keyboard, and disappear for a while. The desk became the coffee shop table, the kitchen table, the coworking bench, the hotel desk. Different furniture, same posture.

That posture used to match the work.

Writing software meant typing everything by hand. The machine waited for you. Every line came through your fingers. A small screen and a touch keyboard were not enough, because production demanded the whole setup: big display, fast keyboard, many files, many panes.

The desk was not arbitrary. It was earned.

But the work has changed.

## The Work Changed

AI did not remove the computer. It changed what you need from it.

More and more, the loop is: describe the change, wait, review, test, adjust, approve. The bottleneck is less often "can I type this fast enough?" and more often "can I tell whether this is right?"

That is still serious work. It may be more serious. Bad judgment ships bad software faster than ever.

But judgment does not always require the full desk ritual. Sometimes it requires the actual diff. The terminal output. The failing test. The log line. The file next to the file that changed. The git state on the machine where the change was made.

Chat alone is not enough.

The AI can suggest. The chat can explain. But the truth is on the computer.

Did the tests pass? What changed? Which files are dirty? What does the app do when it runs? What branch am I on? What did that command print? What is actually in the folder?

Those answers live in the workspace. Not the idea of a workspace. Your workspace.

## Your Computer, Not Someone Else's Instance

The cloud solved a real problem: access.

Put the machine somewhere else and you can reach it from anywhere. That is powerful. For teams, classrooms, disposable environments, and locked-down workflows, it can be the right answer.

But it also changes the relationship. The machine is no longer the one under your desk. The state is somewhere else. The uptime is someone else's. The storage is someone else's. The pricing is someone else's. The environment is something you provision, not something you own.

For a lot of work, that tradeoff is strange.

Your desktop is already on. Your project is already there. Your terminal already has the server running. Your git history is local. Your files are local. Your weird little setup works because you made it work. Why should leaving the room mean leaving all of that behind?

You should be able to reach your computer without moving your work off your computer.

That is the point.

Not "coding on a phone" as a stunt. Not a tiny IDE squeezed into a rectangle. Not a toy terminal. Not a chat app pretending the filesystem is optional.

Your computer. Served to you.

## The Whole Machine

If the code lands in files, you need files.

If the work runs in a shell, you need the shell.

If the truth is in git, you need git.

If the test failed, you need the output.

If an agent is working, you need the session it is working in.

That is why `cptr` is the whole computer in a browser: files, terminal, editor, git, AI, tools, and the state between them. The real operating system. The real filesystem. The real shell. The machine you already use.

Close the tab and the terminal keeps running. Open your phone and the session is still there. Come back to the laptop and nothing has been copied, synced, recreated, or translated into a parallel universe. The work stayed where it belonged.

On your computer.

## The Phone Is The Door

The phone matters because it is the screen you have when you are not at the desk.

It is in your pocket at dinner. It is in your hand on the train. It is next to you on the couch. It is with you when the laptop is not.

That does not mean every task should be done on a phone. Some work wants a large screen. Some work wants a keyboard. Some work wants a chair, silence, and time.

Fine.

The desk should be an option, not a toll booth.

If you need to review a complex change across twenty files, maybe you go to the desk. If you need to check whether the build passed, maybe you do not. If an AI agent needs one clarification, maybe you answer from the sidewalk. If a deploy needs approval, maybe you approve it from the kitchen. If the bug is obvious, maybe you fix it from the train and move on with your day.

The phone is not replacing the workstation.

The phone is how you reach it.

## The Life Around The Work

A developer moves somewhere beautiful and still spends the day in a dark room.

A parent works from home and is technically present, but the closed door says otherwise.

Someone opens a laptop at the beach, cannot see the screen, moves to the shade, then to a cafe, then to an air-conditioned room. The beach was the point. The room is where the work happens. Every time.

These are not failures of discipline. They are failures of access.

When every interaction with your computer requires the desk, every small interaction becomes desk time. Check a build: desk. Read a log: desk. Nudge an agent: desk. Review a diff: desk. Push a fix: desk.

The chair collects hours it did not earn.

Over a forty-year career, at eight hours a day and two hundred fifty working days a year, a knowledge worker spends eighty thousand hours in a chair. Not all of that time is deep work. A lot of it is waiting, checking, approving, reading, responding, and making small decisions around the real work.

Those hours are expensive.

They are the hours when the sun is out. The hours when your kid is awake. The hours when a walk would clear your head. The hours when you could be nearby instead of behind a door.

The point is not to work everywhere.

The point is to stop letting the desk decide where work is allowed to happen.

## The Body

The human body is not designed to be still all day. The research is blunt about this.

Long periods of sitting are associated with higher risks of type 2 diabetes, cardiovascular disease, cancer, and all-cause mortality, even after accounting for physical activity [1]. People who sit eight or more hours per day need 60 to 75 minutes of daily moderate-intensity activity to offset the elevated mortality risk [2]. Most people do not get that. More sedentary time keeps adding risk [3].

Exercise also improves general cognition, memory, and executive function [4]. Walking has been shown to increase divergent thinking compared with sitting [5].

That matters because modern computer work is increasingly judgment work. Reading carefully. Spotting what is wrong. Seeing another approach. Explaining intent clearly. These are not helped by being frozen in one posture all day.

The old interface rewarded stillness because the old work required constant input.

The new work needs clearer thinking.

Movement helps.

## The Interface

Remote access is not enough.

A desktop UI compressed onto a phone is still a desktop UI. Tiny panes. Tiny tabs. Tiny buttons. Tiny misery.

The interface has to be built for the device people actually carry. Touch-native. Portrait-native. Designed for thumbs, interruptions, short checks, and real work that comes in pieces.

That is the remaining distance.

The computer can already serve applications over HTTP. The browser already knows how to render them. The phone already has a screen and a persistent connection. The missing thing is not magic infrastructure. It is an interface that treats the phone as a first-class way to reach the machine, not as a shrunken monitor.

## The Choice

This is not an argument against the desk.

The desk is good. The desk is where deep work often belongs.

This is an argument against needing the desk for everything.

Use the big screen when you want the big screen. Use the keyboard when you want the keyboard. Sit down when sitting down helps.

But when you step away, your computer should not become unreachable.

Your files should still be your files. Your shell should still be your shell. Your git state should still be your git state. Your AI should still be working in the same place. Your sessions should still be alive. Your work should still be on the machine you chose.

Some people already work this way. They sit at the desk for the deep work because they choose to. They check a deploy from the couch. They review a diff while dinner cooks. They push a fix from the train. They pick up their daughter from school and check the build from the bench while she plays. When they need four panes and deep concentration, they go back to the desk. When they do not, they do not.

The computer stays home.

The work stays on the computer.

You do not have to.

---

## References

[1] Biswas, A., et al. (2015). "Sedentary Time and Its Association With Risk for Disease Incidence, Mortality, and Hospitalization in Adults: A Systematic Review and Meta-analysis." *Annals of Internal Medicine*, 162(2), 123-132.

[2] Ekelund, U., et al. (2016). "Does physical activity attenuate, or even eliminate, the detrimental association of sitting time with mortality? A harmonised meta-analysis of data from more than 1 million men and women." *The Lancet*, 388(10051), 1302-1310.

[3] Patterson, R., et al. (2018). "Sedentary behaviour and risk of all-cause, cardiovascular and cancer mortality, and incident type 2 diabetes: a systematic review and dose response meta-analysis." *European Journal of Epidemiology*, 33(9), 811-829.

[4] Maher, C., et al. (2025). "Effectiveness of exercise for improving cognition, memory and executive function: a systematic umbrella review and meta-meta-analysis." *British Journal of Sports Medicine*.

[5] Oppezzo, M. & Schwartz, D.L. (2014). "Give Your Ideas Some Legs: The Positive Effect of Walking on Creative Thinking." *Journal of Experimental Psychology: Learning, Memory, and Cognition*, 40(4), 1142-1152.
