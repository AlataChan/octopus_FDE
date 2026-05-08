from loom.runtimes.hiagent.v2_6.ids import gen_id, is_valid_id


def test_gen_id_length():
    assert len(gen_id()) == 20


def test_gen_id_alphabet():
    s = gen_id()
    assert all(c.islower() or c.isdigit() for c in s)


def test_gen_id_unique():
    values = {gen_id() for _ in range(100)}
    assert len(values) == 100


def test_is_valid_id_accepts_real_sample():
    assert is_valid_id("d7ji7kd4shhcm7cr99hg")


def test_is_valid_id_rejects_uppercase():
    assert not is_valid_id("D7JI7KD4SHHCM7CR99HG")


def test_is_valid_id_rejects_wrong_length():
    assert not is_valid_id("short")
