# Candidate recipe; image contents and inherited base hooks are unverified.
FROM docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b AS dependencies
COPY requirements.txt /build/requirements.txt
COPY wheels/ /build/wheels/
RUN --network=none /usr/local/bin/python -I -m pip install --no-index --find-links=/build/wheels --only-binary=:all: --no-deps --require-hashes --no-compile --disable-pip-version-check --target=/build/site-packages -r /build/requirements.txt

FROM docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b
COPY --from=dependencies /build/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --chown=0:0 --chmod=0444 assets/_guest_common.py /opt/authzest-guest/_guest_common.py
COPY --chown=0:0 --chmod=0444 assets/test_launcher.py /opt/authzest-guest/test_launcher.py
RUN --network=none mkdir -p /opt/authzest-guest /input/tests && touch /input/app.py /input/tests/test_generated_ownership.py && chmod 0444 /input/app.py /input/tests/test_generated_ownership.py && chmod 0555 /opt/authzest-guest /input /input/tests
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python","-I","-B","/opt/authzest-guest/test_launcher.py"]
CMD []
