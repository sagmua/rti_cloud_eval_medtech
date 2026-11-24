# Running a Playground image locally

This helper does not build a standalone image. The former recipe required a legacy prebuilt image that is not distributed with the demo. For an ordinary local run, use the [desktop or browser commands](../docs/local-demo.md).

RTI Cloud maintainers can use the platform's local Playground workflow with an approved, licensed MedTech-capable image. Provision the helper at the IDE workspace root and use the platform's authenticated IDE proxy; do not publish the four device ports separately. In the workspace terminal, run `./scripts/medtech.sh start --cloud`.

The cloud runner uses the Playground's shared Python runtime and the SDK CMake modules exposed by the image for offline builds. Keep the [dependency lock](requirements.lock) and its [direct inputs](requirements.txt) until the shared-Python pilot is accepted. Older pilot image recipes still reference a pinned copy of the lock.
