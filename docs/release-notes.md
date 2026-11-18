# v0.1.0

Initial teaching snapshot: four-command VASP interface, validation and provenance,
editable Slurm template, public Si inputs, optional batch controller, and 21
license-free unit tests. Runtime logic was exercised previously with separately
licensed real Si calculations; output/potential files are not redistributed.

Requirements pin the verified numpy and pymatgen versions. Adapt Slurm/MPI/VASP
paths for each cluster. No protocol/compare command, notifications, automatic
recovery, or live sidebar continuation is included in this snapshot.
