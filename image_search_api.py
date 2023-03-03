import requests

from env import GCD_API_KEY

def get_images(query):
  # Get the images from the google custom search api
  # Google only gives 100 call/day, so be mindful when testing hehe :)
  get_url = "https://www.googleapis.com/customsearch/v1"
  params = {
    "q": query,
    "num": 1,
    "start": 1,
    "imgSize": "large",
    "searchType": "image",
    "filetype": "jpg",
    "key": GCD_API_KEY,
    "cx": "47b694f30fc314a0b"
  }
  response = requests.get(get_url, params=params)
  response.raise_for_status()
  search_results = response.json()
  # Create a list with the links of the images gotten from the search_ and return it
  image_links = []
  for result in search_results['items']:
    image_links.append(result['link'])
  #Return a list of the links of the images
  return image_links
