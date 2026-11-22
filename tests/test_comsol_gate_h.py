"""Real COMSOL 6.4 Gate H integration test (non-solving, opt-in).

Set COMSOL_AGENT_RUN_GATE_H=1 and COMSOL64_HOME=<COMSOL64 root> to run.
Builds a fresh disposable model. It never calls solve(), runAll(), or any
solver run method, and never opens an existing solved model.
"""
from __future__ import annotations

import os

import pytest

from comsol_agent.comsol import ComsolSession

pytestmark = [
    pytest.mark.skipif(os.name != "nt", reason="COMSOL 6.4 Gate H probe requires Windows"),
    pytest.mark.skipif(
        os.environ.get("COMSOL_AGENT_RUN_GATE_H") != "1",
        reason="Set COMSOL_AGENT_RUN_GATE_H=1 to run the local COMSOL Gate H probe",
    ),
]


def test_study_step_xmeshinfo_gives_real_dof_without_solving():
    home = os.environ.get("COMSOL64_HOME")
    if not home:
        pytest.skip("COMSOL64_HOME is not set")
    session = ComsolSession(cores=1, version="6.4", startup_timeout=180, home=home)
    try:
        session.start()
        model = session.client.create("GateHIntegration")
        model.parameter("L", "0.1[m]")
        model.parameter("H", "0.05[m]")
        (model / "components").create(True, name="component")
        geom = (model / "geometries").create(2, name="geometry")
        rect = geom.create("Rectangle", name="plate")
        rect.property("size", ["L", "H"])
        rect.property("pos", ["0", "0"])
        model.build(geom)
        sels = model / "selections"
        hot = sels.create("Box", name="hot")
        hot.property("entitydim", 1)
        hot.property("xmin", 0.0)
        hot.property("xmax", 0.0)
        hot.property("ymin", 0.001)
        hot.property("ymax", 0.049)
        cold = sels.create("Box", name="cold")
        cold.property("entitydim", 1)
        cold.property("xmin", 0.099)
        cold.property("xmax", 0.101)
        cold.property("ymin", 0.001)
        cold.property("ymax", 0.049)
        mat = (model / "materials").create("Common", name="plate material")
        list(mat.children())[0].property("thermalconductivity", "1[W/(m*K)]")
        ht = (model / "physics").create("HeatTransfer", geom, name="heat transfer")
        for name, selection, temperature in (("T1", hot, "100[degC]"), ("T2", cold, "0[degC]")):
            bc = ht.create("TemperatureBoundary", 1, name=name)
            bc.select(selection)
            bc.property("T0", temperature)
        mesh = (model / "meshes").create(geom, name="mesh")
        model.mesh(mesh)
        study = (model / "studies").create(name="stationary")
        study.create("Stationary", name="static")
        study.java.createAutoSequences("all")

        sol = model.java.sol("sol1")
        feature = sol.feature("st1")
        assert str(feature.getType()) == "StudyStep"
        assert sol.isInitialized() is False

        dof = int(feature.xmeshInfo().nDofs())
        per_field = [int(v) for v in list(feature.xmeshInfo().fieldNDofs())]
        assert dof > 0
        assert sum(per_field) == dof
        assert list(feature.xmeshInfo().fieldNames()) == ["comp1.T"]

        # No numerical solution was produced: still uninitialized and no
        # evaluable field. This is the safety boundary of Gate H.
        assert sol.isInitialized() is False
        with pytest.raises(Exception):
            model.evaluate("T", "degC")
        assert len(list(model.problems())) == 0
        assert feature.clearXmesh() is not None
    finally:
        session.close()
