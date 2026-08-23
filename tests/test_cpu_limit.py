from pipeline.cpu_limit import effective_cpus, ffmpeg_thread_args, flam3_nthreads, wrap_cmd


def test_effective_cpus_default_leaves_one(monkeypatch):
    monkeypatch.setattr("pipeline.cpu_limit.host_cpu_count", lambda: 4)
    assert effective_cpus({"render": {}}) == 3


def test_effective_cpus_explicit(monkeypatch):
    monkeypatch.setattr("pipeline.cpu_limit.host_cpu_count", lambda: 4)
    assert effective_cpus({"render": {"max_cpus": 3}}) == 3
    assert effective_cpus({"render": {"max_cpus": 0}}) is None
    assert effective_cpus({"render": {"max_cpus": -1}}) == 3


def test_flam3_nthreads_follows_max(monkeypatch):
    monkeypatch.setattr("pipeline.cpu_limit.host_cpu_count", lambda: 4)
    assert flam3_nthreads({"render": {"max_cpus": 3}}) == 3
    assert flam3_nthreads({"render": {"max_cpus": 3, "flam3_nthreads": 2}}) == 2


def test_ffmpeg_thread_args(monkeypatch):
    monkeypatch.setattr("pipeline.cpu_limit.host_cpu_count", lambda: 4)
    assert ffmpeg_thread_args({"render": {"max_cpus": 3}}) == [
        "-threads",
        "3",
        "-filter_threads",
        "3",
    ]


def test_wrap_cmd_taskset(monkeypatch):
    monkeypatch.setattr("pipeline.cpu_limit.host_cpu_count", lambda: 4)
    monkeypatch.setattr("pipeline.cpu_limit.shutil.which", lambda _name: "/usr/bin/taskset")
    assert wrap_cmd({"render": {"max_cpus": 3}}, ["flam3-animate"]) == [
        "taskset",
        "-c",
        "0-2",
        "flam3-animate",
    ]
