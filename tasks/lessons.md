# Lessons

- Always use Conventional Commits for git commit messages in this repo.
- Before running `git commit`, explicitly verify the message follows the `<type>: <summary>` format.
- When the user asks for helper scripts to be parameter-driven, use positional arguments instead of environment-variable-driven configuration.
- When changing CLI flags, confirm whether the default behavior should remain backward-compatible; do not assume that adding an opt-out flag means the default should flip.
