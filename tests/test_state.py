from vpnforge.state import load_state, update_state


def test_state_is_merged_and_persisted(paths):
    assert load_state(paths)["installed"] is False
    update_state(paths, installed=True, nginx_stage="final")
    state = load_state(paths)
    assert state["installed"] is True
    assert state["nginx_stage"] == "final"
