# Sao chép gói về AIO-mesh-submit-2

Gói: `/home/CoreRouter/results/export/hil_rev1_20261121/` (~70 MB) và bản nén `/home/CoreRouter/results/export/hil_rev1_20261121.tar.gz` (SHA-256 trong `hil_rev1_20261121.tar.gz.sha256`).

Cùng máy (thư mục `AIO-mesh-submit-2` đang được git theo dõi):

```bash
cd /home/CoreRouter/results/export/hil_rev1_20261121 && /home/CoreRouter/venv/bin/python scripts/check_export.py .
mkdir -p /home/CoreRouter/AIO-mesh-submit-2/results/hil_export
rsync -a --checksum /home/CoreRouter/results/export/hil_rev1_20261121/ \
      /home/CoreRouter/AIO-mesh-submit-2/results/hil_export/hil_rev1_20261121/
cd /home/CoreRouter/AIO-mesh-submit-2/results/hil_export/hil_rev1_20261121 && sha256sum -c --quiet SHA256SUMS && echo OK
cd /home/CoreRouter/AIO-mesh-submit-2 && python3 scripts/rev1/refresh_submission_manifest.py
```

Từ máy khác (máy chứa bản AIO-mesh-submit-2 chính), kéo bản nén rồi kiểm:

```bash
scp <user>@<testbed-host>:/home/CoreRouter/results/export/hil_rev1_20261121.tar.gz{,.sha256} .
sha256sum -c hil_rev1_20261121.tar.gz.sha256
mkdir -p AIO-mesh-submit-2/results/hil_export
tar -xzf hil_rev1_20261121.tar.gz -C AIO-mesh-submit-2/results/hil_export
(cd AIO-mesh-submit-2/results/hil_export/hil_rev1_20261121 && sha256sum -c --quiet SHA256SUMS && echo OK)
```

`check_export.py` tái sinh bảng cần repo `/home/CoreRouter` (venv, `scripts/paper/make_table11.py`, `infrastructure/sdn/p4_topology.py`) và `tcpdump`; ở máy khác chỉ chạy được `sha256sum -c SHA256SUMS`. Chưa gửi dữ liệu ra ngoài và chưa commit.
