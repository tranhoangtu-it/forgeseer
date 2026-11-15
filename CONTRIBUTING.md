# Contributing

Thanks for taking a look.

## Bugs and ideas

Open an issue using one of the [templates](https://github.com/tranhoangtu-it/forgeseer/issues/new/choose).
The ForgeSeer version, the in-game day and a screenshot of the overlay help a lot.

## Working on the code

```bash
pip install pytest frida
python -m pytest -q
python -m forgeseer
```

- [docs/technical-notes.md](docs/technical-notes.md) has the architecture and what's known about
  the game's internals.
- Logic lives in plain functions with pytest tests; please add a test with your change.
- Overlay text goes in `forgeseer/locales/*.json`. Add new keys to every language file (English is
  fine as a placeholder if you don't speak one of them, just say so in the PR).
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`...).

## Hard rules

- Read-only: never write game memory or the save file. Simulations only run on fresh copies.
- No predicting outcomes from the game's RNG state.
