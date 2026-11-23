# Separate external-workflow candidate; not built or runtime accepted.
FROM docker.io/library/python@sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4 AS dependencies
COPY requirements.txt /build/requirements.txt
COPY wheels/ /build/wheels/
RUN --network=none /usr/local/bin/python -I -m pip install --no-index --find-links=/build/wheels --only-binary=:all: --no-deps --require-hashes --no-compile --disable-pip-version-check --target=/build/site-packages -r /build/requirements.txt

FROM docker.io/library/python@sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4
COPY --from=dependencies /build/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --chown=0:0 --chmod=0444 assets/_guest_common.py /opt/authzest-repository-guest/_guest_common.py
COPY --chown=0:0 --chmod=0444 assets/_repository_manifest.py /opt/authzest-repository-guest/_repository_manifest.py
COPY --chown=0:0 --chmod=0444 assets/app_launcher.py /opt/authzest-repository-guest/app_launcher.py
RUN --network=none mkdir -p /opt/authzest-repository-guest /input /input/project && chmod 0555 /opt/authzest-repository-guest /input /input/project
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python","-I","-B","/opt/authzest-repository-guest/app_launcher.py"]
CMD []
