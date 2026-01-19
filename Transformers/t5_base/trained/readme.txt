docker build -t nl2sparql .


docker run -d --name nl2sparql_service --hostname nl2sparql-host --restart always -p 6005:6005 -v $(pwd)/checkpoint-2:/app/checkpoint-2 -v $(pwd)/app.py:/app/app.py --network nl2sparql_t5_network suhas_nl2sparql




1. Build the Docker image

docker build -t suhas_nl2sparql .
2. Create the Docker network (only once)

docker network create nl2sparql_t5_network
3. Run your app container

docker run -d \
  --name suhas_nl2sparql_service \
  --hostname nl2sparql-host \
  --restart always \
  -p 6005:6005 \
  -v $(pwd)/checkpoint-2:/app/checkpoint-2 \
  -v $(pwd)/app.py:/app/app.py \
  --network nl2sparql_t5_network \
  suhas_nl2sparql
4. Run your ngrok container

docker run -d \
  --name ngrok-nl2sparql_suhas \
  --network nl2sparql_t5_network \
  -e NGROK_AUTHTOKEN=2vYIEAi19a7QihZjdxMG2ABRTp4_5PHERtFfK84tvikowvXdW \
  -e NGROK_REGION=Global \
  -p 4045:4040 \
  ngrok/ngrok:latest http suhas_nl2sparql_service:6005 --domain=deep-gator-cleanly.ngrok-free.app
