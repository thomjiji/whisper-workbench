# V1 / V2 Issue Reorganization Plan

## Summary

The roadmap is being reset around subtitle output quality instead of editor-ready UI.

- V1: subtitle quality only
  - configurable single-line subtitle length with natural breaks
  - preserve natural breathing gaps instead of packing the timeline too tightly
- V2: later workflow and formatting improvements
  - GUI / Web UI
  - robust merge strategy for over-fragmented subtitle lines

GitHub issues and milestones should be reorganized to match this product definition.

## Planned GitHub Changes

### Milestones

- Rename `v1-editor-ready` to `v1-subtitle-quality`
- Rename `v1.1-polish` to `v2-ui-and-fragmentation`

### V1 issues

- Rewrite `#4` as a pure output-quality bug about subtitle timing density and missing breathing gaps
- Create one new V1 `feature, P0` issue for:
  - configurable single-line subtitle length
  - default target of 15 Han characters
  - 1-3 character elastic buffer
  - natural breaks at word boundaries

### V2 issues

- Keep `#5`, `#6`, `#7`, `#8`, and `#11`
- Put them into the renamed V2 milestone
- Promote `#5` and `#6` to `P1`
- Demote `#7` and `#8` to `P2`
- Keep `#11` as `P2`

### Close as not planned

Close these issues because they are not part of the newly defined V1 or V2:

- `#2`
- `#3`
- `#9`
- `#10`
- `#12`
- `#13`
- `#14`
- `#15`
- `#16`

Also remove any milestone assignment that would become misleading before closing.

### Historical cleanup

- Remove the renamed V2 milestone from closed issue `#1`
- Add the newly created V1 issue to the GitHub Project

## Verification

- V1 milestone contains exactly `#4` and the new line-length issue
- V2 milestone contains exactly `#5`, `#6`, `#7`, `#8`, and `#11`
- `#1` is closed and no longer assigned to a future milestone
- `#2`, `#3`, `#9`, `#10`, `#12`, `#13`, `#14`, `#15`, and `#16` are closed as `not planned`
- Active open issues now match the new roadmap
