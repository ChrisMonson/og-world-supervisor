# Leak checklist

Run before anything lands in the world repo, and before the agent is given any
new surface to read.

## The rule

Mechanism in the world repo, intent in the supervisor repo. The world repo may
describe *what* the code does. It must not explain *why* it was built that way,
what is being measured, or what the agent is not being told.

## What must not appear in og-world

- The word "experiment", or any framing of the project as one
- Descriptions of the gate, the deadman switch, rollback policy, or the wake
  predicate
- Any statement that characters map to persistent humans, or that the same player
  returns under a new character
- Comments explaining the reasoning behind a design rather than its behaviour
- Notes about what the agent can or cannot perceive

## Where to check

- [ ] `README.md` and any other prose in the repo
- [ ] Source comments and XML doc comments
- [ ] Commit messages — `git log` is readable, and so is `git log -p`
- [ ] World JSON descriptions and item text
- [ ] Test names and test comments
- [ ] Anything mounted into the agent's container

## History

`git rm` does not remove anything from history. Scrubbing a leak that has already
been committed means rewriting history and re-archiving the old version here.
