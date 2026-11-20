# Extend a reviewed, locally available, platform-specific AuthZest T dependency image.
ARG OWNER_READ_TEST_BASE
FROM ${OWNER_READ_TEST_BASE}
USER 0:0
# Remove the previous maintained scenario's input placeholders in the image only.
RUN ["/usr/local/bin/python", "-I", "-B", "-c", "from pathlib import Path; p=Path('/input'); (p/'app.py').unlink(); (p/'tests/test_generated_ownership.py').unlink(); (p/'tests').rmdir(); assert not list(p.iterdir()); (p/'availability.py').touch(mode=0o444); (p/'test_owner_archived_read.py').touch(mode=0o444)"]
COPY package/ /usr/local/lib/python3.12/site-packages/
COPY assets/ /opt/authzest-owner/
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python","-I","-B","/opt/authzest-owner/guest.py"]
CMD []
