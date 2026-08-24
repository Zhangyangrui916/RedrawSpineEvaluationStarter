# Assets

`public_static_mesh_smoke` is a candidate-visible renderer and interface smoke asset. It is not a hidden evaluation instance and retains the original character RGB only for forward-render validation.

`cases/static_mesh_seed_a` and `cases/static_mesh_seed_b` are complete candidate-visible final task inputs. They contain low-information S0 pages and 1:1 before/after observations, but no S1 pages, trusted support masks, hidden poses, reference frames, or grader data.

`dev_cases/synthetic_dev` is a fully public development oracle. Its `oracle/` directory intentionally contains S1 pages and validation references. It is not a final scored instance and uses a different target seed.
