# V2 Assets

`cases/real_art_continuous_run8` is the complete candidate-visible final input. It contains S0 and ten before/after
observations, but no target S1, trusted support, hidden poses, references, or grader data.

`dev_cases/real_art_continuous_dev_run12` is a fully public development oracle using an independent redraw. Its
`oracle/` directory contains S1 and validation references. `operator_energy/aggregate/` contains float32 per-texel
coefficient-energy maps and PNG visualizations.

The public development target is diagnostic data, not the answer to the final Run 8 case.
