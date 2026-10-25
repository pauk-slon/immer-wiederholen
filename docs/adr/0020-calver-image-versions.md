# 0020. Image versions are calendar-based

**Status:** Accepted, 2026-10-25 ([#300](https://github.com/pauk-slon/immer-wiederholen/pull/300)).

## Context

Every merge into `main` builds the image and deploys it. Before this decision, the image had one tag, `:main`, which moved with every build. Only the `org.opencontainers.image.revision` label told which commit an image contained. A rollback to an earlier build needed a revert and a new build, because no tag pointed to the earlier image.

The main goal is a version that people can read and say. A request like "roll back to 2026.10.3" must be easy to say, write and remember, and it must not be a commit hash. The second goal is order. Of two versions, a person must see which build is newer without a lookup. A commit hash gives neither. The `version` in `pyproject.toml` stays `0.1.0`, because the project isn't published as a package and nothing reads it.

## Decision

Each build gets a version in the format `YYYY.M.N`, for example `2026.10.3`:

- `YYYY.M` is the year and the month of the commit, in UTC, with no leading zero in the month.
- `N` is the number of the commit among the commits on `main` in that month. It starts at 1 every month.

The publish workflow calculates the version from the git history. It isn't stored in the repository and isn't a git tag. The repository allows only squash merges, so the history of `main` is linear and every commit on it is one merged pull request. The same commit always gets the same version. Two builds that run at the same time can't get the same version.

The month is calculated in UTC, because the commit dates on `main` have the time zone of the person who merged the pull request.

The version is used in three places:

- the image tag, such as `:2026.10.3`, next to `:main`,
- the `org.opencontainers.image.version` label,
- the `service.version` resource attribute of the traces, through the `APP_VERSION` variable that the image sets.

The format is valid and canonical under PEP 440. It is also valid SemVer, so tools that expect `MAJOR.MINOR.PATCH` sort it in the same order.

## Alternatives considered

- **Commit hash as the tag.** Not chosen, because a person can't say or remember it, and it doesn't show which build is newer.
- **One counter, such as the number of commits on `main`.** It is easy to say and shows the order. Not chosen, because a number like `272` tells nothing about the date of the build. A single number also isn't valid SemVer.
- **SemVer.** Not chosen, because the service has no consumers that would read a major or minor change from the number. Each bump would be a manual decision with no use.
- **A per-deploy counter in git tags.** It would have no gaps when a build fails. Not chosen, because the version would depend on state outside the commit, and two builds at the same time could take the same number.
- **A zero-padded month, `YYYY.0M.N`.** Not chosen, because PEP 440 normalizes `2026.01` to `2026.1`, and the leading zero makes the version invalid SemVer.

## Consequences

- A person can name a build in speech or in a message, for example "roll back to 2026.10.3".
- A larger version is always a newer build. A person can compare two versions without a lookup.
- A deploy can use a specific version tag, and a rollback to an earlier build needs no new build.
- `N` counts all merges, also those whose checks failed and that weren't published. The published versions can have gaps, for example `2026.10.4` and then `2026.10.6`.
- A pull request merged just before midnight UTC on the last day of a month gets that month, even if it was already the next month for the person who merged it.
- A locally built image has no version, and its spans have no `service.version`.
