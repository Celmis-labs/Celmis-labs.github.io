A review tool has two ways to lose a team's trust. It can miss the defect, or it can talk so much that people stop reading it. The second one is cheaper to cause and harder to notice, because every comment looks defensible on its own.

Release 3.1.1 of Celmis is about the second failure.

## The bug that counted what it hid

Celmis lets a repository set a comment level, the lowest severity worth interrupting a person for. Below it, a finding is kept for the web app and left out of the inline comments.

That was only half the rule. The summary comment and the pull request description still counted the hidden findings. A reviewer could write "1 warning" under a pull request where there was nothing to read, and the same hidden finding turned an approval into a plain comment. The setting kept the noise out of the diff and let it back in through the front door.

Now the counts, the breakdown, the verdict and the description are all computed from the findings at or above the level. A review with nothing at or above it approves. What forbids an approval is unchanged: a failed critical agent, a blocking compliance finding, an incomplete review, an installation with approvals switched off. When one of those applies, the comment says so in one line.

One consequence is worth stating plainly, because it changes behaviour. Under a "critical only" level, errors no longer request changes, since they are below the level. A repository that wants warnings to hold a pull request back sets the level to `warning`.

## A comment is the problem, the reason and the fix

The finders are asked for a title that is one line stating the problem, at most two short sentences of body that do not repeat the reason, and the concrete fix, with code when there is code. No preamble, no retelling of the code, no hedging, no advice that would fit any code. The closing comment follows the same rule: one verdict line, the number of inline comments, anything that did not fit under the per-review cap, and the two commands that matter. An approval is a heading and one line.

## In the language the repository chose

A review in Ukrainian used to arrive with its reasoning sentence in English, because the language instruction named titles and bodies and not the field that opens every finding, and the prompt's examples were English. The instruction now names every field a person reads, comes after the output format, and is repeated as the last line of the request.

Instructions are not a guarantee, so there is a check after them. Once the findings are final, the text that will be posted goes through a cheap deterministic test: a sentence in the wrong script, or, for Latin-script languages, a sentence made of English function words. What fails is rewritten in one batched call. A finding is never dropped for its language, a finding a program proved is never touched, and a rewrite that lost a piece of code is not used. The check can add one model call to a review, and only when a comment fails it.

## What it does not claim

The language check cannot tell Ukrainian from Russian, and for Latin-script languages it is best effort. The position of this release on the public benchmark is also unchanged because it has not been measured again: the 17th place of 50 predates these changes, and the review has changed a lot since. When there is a new number it will go on the page with the command that reproduces it.

Release notes and upgrade steps are in the [changelog](https://github.com/Celmis-labs/Celmis/blob/main/CHANGELOG.md). The reviewer's commands are in the [documentation](/docs/guide/#talking-to-the-reviewer-and-what-it-learns).
