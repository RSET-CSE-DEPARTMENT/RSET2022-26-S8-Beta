FROM debian:stable-slim

# install tor and ca-certificates
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y tor ca-certificates && rm -rf /var/lib/apt/lists/*

# tor will run with the config mounted at /etc/tor/torrc
ENTRYPOINT ["tor", "-f", "/etc/tor/torrc"]
