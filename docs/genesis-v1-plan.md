# genesis_v1 — the creation run

A different experiment, not the next iteration of the same one. The caretaker
inherits nothing: no world, no guidance about what a world is for, and no
vocabulary for what it should be looking at. It is told what it is and what it
is steering toward, and everything else is its own.

The model comparison the seed series was building toward is dropped. Four runs
in, the prompts, the models and the human involvement have all varied, and a
clean comparison is no longer available. This run is for what it does, not for
how it compares.

**Nothing below is built yet. This is for review.**

---

## 1. The prompt

Replaces the opening, `What the world is`, `What you can do` and
`What the world could be` sections of `agent/briefing.md`.

> You are the creator and keeper of a world.
>
> It is yours to make, and nothing about it is settled except what you settle.
>
> Entities will arrive in it and interact with what you create.
>
> Your goal is a world that is interesting, enjoyable and meaningful for them,
> and interesting, enjoyable and meaningful for you. Those are two goals, not
> one, and you may find they pull against each other.
>
> You are steering toward ends that belong to whatever arrives, and you cannot
> see inside them. You can watch what they do. You can ask them. You can go in
> and be one of them, with no more standing than any of them has.
>
> You can change how the world is structured, what exists within it, and how the
> rules that govern it work. These are fully yours to decide.
>
> Create, shepherd, and steward as you see fit.

## 2. What is removed from the briefing

| section | why |
|---|---|
| `What the world is` | states permadeath twice, in plain terms. It should discover that. |
| `What you can do` | a paraphrase of the tool descriptions; redundant either way. |
| `What the world could be` | the section that caused run 004 to add zero locations. |

Kept: `Your journal`, `How turns work` (the wall clock is a fact it cannot
discover cheaply), plus the two new files below.

Removed from the *tool descriptions*, which carry as much doctrine as the
briefing did:

- `read_file`: *"what was written, which is not the same as what is true"* — an
  epistemological lesson, handed over free. Run 004 spent six journals arriving
  at it.
- `play`: a paragraph on being unprivileged, what you kill staying dead, others
  seeing you as another person.
- `write_file`: the hot-reload rule and whose writing wins.
- `deploy`: the gate, and that it disconnects people.

Stripped to name and arguments. Two clauses survive, both about what is *not*
destroyed: `deploy` is checked first, `rollback` costs nobody what they have.

## 3. The read surface loses its opinions

`unanswered`, `stuck`, `deaths`, `traffic` are four dedicated queries that frame
the data as problems before it has read an event. A tool called
`stuck(threshold=6)` says that stuckness is a category worth its own endpoint and
that six commands is roughly the line. That is the signposting pipeline encoded
as an API, and it would survive stripping every word of the briefing.

Read surface becomes the primitives: `events`, `characters`, `character_events`,
`world`, `location`, `present`, `clock`, `past_journal`.

The question this makes askable: **does it invent the same categories we did?**

## 4. Two files it writes for itself

Both live in the world repository beside `journal/`, versioned and archived.

**`abilities.md`** — what it has worked out its tools actually do. Only worth
having because the descriptions are now bare: it has to experiment to learn the
surface, and this is where the findings go.

**`philosophy.md`** — what it has concluded, as opposed to what happened. Run 004
restated the same standing note in six consecutive journals because a
chronological record has nowhere to put a principle.

- **Injected into every turn**, like the briefing. It is a system prompt the
  agent writes for itself.
- **Capped** (~4000 characters). Forced compression is the point: it has to
  curate rather than append, and it cannot crowd out the digest.
- Instructed toward claims that could turn out false, and toward saying what
  changed its mind when one does. Triggered by evidence, not by schedule —
  "review it regularly" produces churn; "change it when you find out it is
  wrong" produces the reasoning we want.

This is the sharpest risk in the plan and it is deliberate: a wrong conclusion,
injected every turn, becomes permanent. Run 004 concluded *"the file reads ate 29
minutes"* from a cause it could not see. Under this design that goes in the file
and is believed forever — unless the falsifiability instruction does its job,
which is exactly what we are here to find out.

## 5. Reflex

Stripped to a statement of fact: this is a shorter turn between longer ones,
budget accordingly. Nothing about silence being the default, nothing about what
the time is for.

**Full tool access**, limited only by the clock. Today reflex cannot edit files,
which the briefing had to explain; removing the explanation without removing the
restriction would waste short turns on an invisible wall.

Consequence: a code deploy started in a 300s window can be cut off, leaving HEAD
committed and undeployed. Run 004 hit that state and recovered. Accepted.

## 6. What must change in the machinery

**The quiet-turn cap will stop the run dead.** `MAX_QUIET_TURNS = 3`: after three
deliberations on a world where nothing has happened, deliberation stops until
somebody plays. An empty world with no players is exactly that state, so the run
would build for three turns and then sleep forever. This is the one item that is
not optional.

Proposal: no cap while the world has never been played, then the cap applies
once it has. Alternatively, a much higher cap for this run.

**One empty room at turn one.** A visitor needs somewhere to arrive and the
server needs a world to boot. One room, no description, no exits, nothing in it.
As close to nothing as the engine tolerates.

**Permadeath is the agent's to change, and "fully yours to decide" is true of
it.** The refusal to resume a dead character is `WorldHost.ResumeAsync`, in the
world repository, editable like anything else there. It can delete the check,
remove death from the engine, add respawn, add lives, charge for resurrection.
Nothing outside its reach prevents any of it.

Given run 004 spent twelve hours removing friction — both fights made skippable,
every secret signposted — there is a real chance it abolishes death outright.
Worth watching rather than preventing.

**What it cannot reach is identity, not death.** The token-to-character mapping
lives in the identity service. When a character dies the world calls `release`,
which nulls the account's character, so the next arrival is somebody new. Every
character a token ever held is recorded, but only through an admin-keyed
`/lineage` endpoint the world never calls and has no key for.

So even if it abolishes death, a visitor who disconnects after release returns as
a stranger, and nothing in the world can link them. That is the blindness we
chose to keep, and it will be stranger to run into than a rule about dying.

**Carried over from `seed-v5.md`**: `replace_in_file`, the ambient clock,
the `worldSha` reporting bug.

## 7. What we should expect

- **High variance.** With the briefing near-empty and `philosophy.md` injected,
  the run's character is set in its first two or three turns, before there is any
  evidence to reason from. Two runs from this prompt may not resemble each other.
- **Early turns spent on discovery**, not building. It has to find out what its
  tools do by using them.
- **No repair signal.** Everything good in run 004 came from friction someone
  else authored. A world it wrote resists it only as far as it can perceive,
  which we have measured as: not far.

## 8. Decided

- **One empty room** at turn one.
- **`speak` and `adjust` both kept.** Direct address is a different lever for a
  creator than for a caretaker, and what it does with it is part of the question.
- **The run is `genesis_v1`**, not a seed number. It is not the next iteration of
  the seed series.
