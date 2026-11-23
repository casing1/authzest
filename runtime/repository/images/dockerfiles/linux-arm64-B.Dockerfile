# Separate external-workflow candidate; not built or runtime accepted.
FROM docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b
COPY --chown=0:0 --chmod=0444 assets/_guest_common.py /opt/authzest-repository-guest/_guest_common.py
COPY --chown=0:0 --chmod=0444 assets/repository_http.py /opt/authzest-repository-guest/repository_http.py
COPY --chown=0:0 --chmod=0444 assets/relay_launcher.py /opt/authzest-repository-guest/relay_launcher.py
RUN --network=none mkdir -p /opt/authzest-repository-guest /input && chmod 0555 /opt/authzest-repository-guest /input
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python","-I","-B","/opt/authzest-repository-guest/relay_launcher.py"]
CMD []
