# Architecture — v30.1.0 "Personalize"

## Product contract

The five primary labels are Home, Apps, Tweaks, Health, and Updates. Their
underlying Install, Tune, Fix, and Update route IDs remain valid. Activity &
Recovery remains the secondary history and reboot follow-up view. CLI commands,
saved action IDs, and schema-v4 plans/runs are unchanged.

## Tweak boundary

`core/tasks/tweaks.py` declares eight closed controls and reads current state
with the existing read-only runtime. It scopes visibility by the immutable
Fedora desktop and deployment profile. GNOME controls have fixed keys/values;
KDE color choices are obtained from installed schemes and arbitrary animation
values remain visible without mutation. Power choices are read from the host.

`core/actions/tweaks.py` binds each control to one registered action ID, fresh
preflight, typed command rendering, and independent post-run readback. The
shared orchestrator, command facade, and operation controller retain policy,
durability, lease, confirmation, and verification authority. The executor
policy admits only the reviewed GNOME keys and KDE operation shapes.

`ui/tweaks_page.py` presents searchable rows, current values, availability,
busy state, and verified results. The main window owns the Qt worker and
reloads actual state after each attempt. The page never executes a command.

## Health and compatibility

Health owns symptom diagnosis, storage trim, and package cache cleanup. Legacy
action requests open a review on Health; saved System Check findings are
re-resolved by fingerprint before a plan is reviewed. No normal workflow opens
the internal Action Center view. Old links to that view open Activity.

## Qualification boundary

Offscreen and mocked tests check state, policy, route compatibility, and
readback. Physical GNOME, KDE, Polkit, keyboard, Orca, and Atomic verification
must be reported independently. Publication and installation are outside this
candidate.
