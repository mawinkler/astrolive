#!/bin/bash
docker run --volume /fits:/fits:ro --name astrolive --rm astrolive
docker logs -f astrolive