# Public V2 Development Oracle

This fixture intentionally exposes S1 and validation references. Use it to validate a reconstruction method before
running the same method on the final Run 8 case. The final case does not expose S1, coefficient-energy maps, trusted
support masks, hidden poses, references, or a score oracle.

`operator_energy/aggregate/*.energy.f32` stores little-endian float32 per-texel `max_rgb(sum_p(A[p,t]^2))` values.
The PNG beside each raw map is a visualization only. These maps are diagnostic data, not candidate-submitted masks.
