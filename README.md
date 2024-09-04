## Dynamic Drafting with ChatGPT API
This is a rough slapped together attempt to take in dynamic rosters and picks during a snake draft on ESPN. These values are passed to ChatGPT through an API call to provide a recommended pick given internal knowledge and expert rankings from TheScore and FantasyPros.

You need to first set up an API key with OpenAI and set it to your environment variable 'OPENAI_API_KEY'

Additionally, you will need to download geckodriver.exe to use selenium with Firefox.

This is an assistant to drafting and will not auto draft for you. You will still have to take the recommendation and select it yourself.

The way I pull the data is VERY brittle, any change would break the methods for getting the XPATH.
