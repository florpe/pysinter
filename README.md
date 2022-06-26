
# pysinter, a FUSE library

- Operates on a file descriptor either passed directly or contained in an environment variable
- Separates the FUSE protocol details from the interaction with the FUSE fd
- Async ready using the Janus queue library - fd operations should be run in a thread
- Dynamically generates a client from a protocol description, to be obtained e.g. from the sinter documentation


