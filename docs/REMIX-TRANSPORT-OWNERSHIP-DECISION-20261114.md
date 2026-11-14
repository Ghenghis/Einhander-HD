# Remix transport ownership decision — November 14, 2026

DECISION: The native producer publishes immutable owned frame descriptions; the Remix consumer owns persistent mesh IDs, cache retirement and SDK resources.

BECAUSE: The current capture, native renderer and asynchronous Remix lifecycle have different owners and lifetimes. A stateless producer cannot safely decide reuse or eviction in a consumer-owned cache.

ALTERNATIVE: Producer-assigned persistent IDs with a separate cross-thread resource and retirement protocol. This would require more shared state and acknowledgement rules before it provides useful rendering evidence.

COST: The pilot copies bounded geometry/material keys and resolves cache identities on the consumer. Copy cost, queue drops, cache misses and GPU completion remain measured acceptance work; no speedup or motion-vector quality is assumed.

REVERSIBLE: Yes before live integration; the native default is unchanged and no installed release depends on this transport.

This is a source design decision, not an implemented backend. [Current executed results and remaining integration](CPU-ENGINE-SOURCE-CONTINUATION-20261114.md).

The producer must not publish pointers into capture storage, decode-cache entries or GL resources. It gives the consumer an owned frame containing canonical content keys, copied geometry, draw order, native source/frame generations and material identifiers. The consumer resolves `new` versus `reuse` and assigns IDs. A full content comparison follows hash lookup; hashes are not equality proofs. The consumer retires only resources no pending or in-flight frame uses. CPU geometry construction and CPU cache resolution need separate explicit APIs and controls.

A single pending slot needs a conditional publish into an empty slot. An unconditional exchange that overwrites an occupied pointer would lose ownership. Count a busy drop and release only the unpublished frame. Capacity accounting must include the producer's building frame, the pending frame and the consumer's in-flight frame. Fixed storage limits and allocation failures must select a complete native fallback, with no partial suppression of primitives.

Reprojection of the view-space payload is necessary but insufficient for model-space transport. Before using copied model vertices and RT/TR, recompute all three raw accumulators and compare them with the captured MAC values. Validate domain and overflow independently of claimed flags. A stale or colliding transform record must not produce a different Remix shape while passing a GTE-only screen check. Widescreen/dome cases outside the oracle remain native until explicitly supported.

Raw textured polygons retain PS1 per-texel STP transparency semantics: “raw” bypasses color modulation. It does not turn a textured semi-transparent polygon into a whole-polygon blend. Both modulated and raw textured semi-transparent polygons need equivalent opaque/semi texel treatment. Untextured semi-transparent polygons blend as a whole. Mask bits, texture windows and painter order remain explicit qualification requirements.

The live compositor must treat presentation as a frame transaction. A CPU transport disposition alone cannot authorize skipping native geometry. The exact frame/source generation, successful resource submission, completed interop image and matching overlay order must agree before presentation. If the consumer drops, fails or misses its bounded readiness window, present the complete native frame. Reusing a previous Remix image with current native overlays would need a separate temporal design and cannot be an implicit fallback.

The first GPU milestone remains a captured-frame diagnostic: compare one qualified scene against its native silhouette and then its material/blend semantics. A later live stream requires the presentation transaction and fallback tests. View-space camera output alone qualifies neither stable world lighting nor DLSS motion data. No renderer rewrite, RT/DLSS acceptance or performance improvement is established by this decision.
