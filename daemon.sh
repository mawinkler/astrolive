#!/bin/bash
docker run --volume /fits:/fits:ro --name astrolive --rm -d astrolive
docker logs -f astrolive