# 0023. The registry keeps the images of the last 30 versions

**Status:** Accepted, 2026-10-25. The feature is discussed in [#303](https://github.com/pauk-slon/immer-wiederholen/issues/303).

## Context

Every publish adds an image to `ghcr.io/pauk-slon/immer-wiederholen`, and nothing deleted the old ones. Before [ADR 0020](0020-calendar-version-per-commit.md), each build took the only tag, `:main`, from the previous build. A new build of the same version still moves its tag to the new image. So the registry collects images without a tag.

The deploy is a manual step, so production can be several versions behind `main`. A rollback uses the version tag of an earlier commit (see ADR 0020).

## Decision

After each publish, the workflow deletes all package versions without a tag. Then it deletes the tagged versions that are older than the 30 newest. [Configuration](../configuration.md) describes this for operators.

An image is one manifest, without an index or attestation manifests. The workflow turns off provenance and SBOM to keep it so. Otherwise the child manifests of a tagged image would have no tag, and the first step would delete them.

## Alternatives considered

- **Keep the 10 newest versions, tagged or not.** This was the first proposal in [#303](https://github.com/pauk-slon/immer-wiederholen/issues/303). Not chosen, because untagged images from new builds of the same version take places among the 10. Also 10 versions can pass between two deploys, and then the image that production runs is deleted.
- **Delete only versions without a tag.** Not chosen, because the tagged versions would still grow without a limit.
- **Delete versions older than a number of days.** Not chosen, because the number of versions in a period changes a lot. A quiet month would keep almost nothing to roll back to.
- **Keep the version that production runs.** Not chosen, because the workflow doesn't know which version is deployed.

## Consequences

- A rollback can go to any of the 30 newest published versions, not to every earlier one as ADR 0020 says.
- If production is more than 30 versions behind `main`, its image is deleted. The container keeps working, but the image can't be pulled again.
- A build for several platforms, or with attestations, needs a different way to delete untagged versions.
