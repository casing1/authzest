# Candidate recipe; image contents and inherited base hooks are unverified.
FROM docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b
COPY --chown=0:0 --chmod=0444 assets/_generated_repair_http.py /opt/authzest-guest/_generated_repair_http.py
COPY --chown=0:0 --chmod=0444 assets/_guest_common.py /opt/authzest-guest/_guest_common.py
COPY --chown=0:0 --chmod=0444 assets/relay_launcher.py /opt/authzest-guest/relay_launcher.py
RUN --network=none mkdir -p /opt/authzest-guest && chmod 0555 /opt/authzest-guest
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python","-I","-B","/opt/authzest-guest/relay_launcher.py"]
CMD []
