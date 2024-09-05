## Dynamic Drafting with ChatGPT API
This is a rough slapped together attempt to take in dynamic rosters and picks during a snake draft on ESPN. These values are passed to ChatGPT through an API call to provide a recommended pick given internal knowledge and expert rankings from TheScore and FantasyPros.

You need to first set up an API key with OpenAI and set it to your environment variable 'OPENAI_API_KEY'

Additionally, you will need to download geckodriver.exe to use selenium with Firefox.

This is an assistant to drafting and will not auto draft for you. You will still have to take the recommendation and select it yourself.

The way I pull the data is VERY brittle, any change would break the methods for getting the XPATH.

## Rough Setup Guide

First, generate your own virtual environment and install the frozen requirements:

https://docs.python.org/3/tutorial/venv.html

https://pip.pypa.io/en/stable/cli/pip_freeze/

Next, download the geckdriver, (see readme in .drivers for geck release url)

Lastly, if you want to use the ChatGPT API, you will have to gernerate your own API Keys: 
https://platform.openai.com/api-keys

Once you have it, you will need to set it to a global environment variable 'OPENAI_API_KEY'
https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety

## Rough Run Guide

Once your draft has started, you will want to copy the URL to that specific draft.

Then, run the Initialize Library and OpenAI Client step, the Import to DataFrames step, and the Starting Firefox Service step.
  Here you will take the copied URL and past into the input request in the notebook.

Next, sign into your ESPN account.

Once that is done, you can run the GPT Script once the draft has started. It will print out the recommend pick and then wait for you to provide it any additional information for the next round of drafting.
**NOTE** It's built to send a prompt everytime you hit enter, so only hit enter when you are ready.

Lastly, once you are done. Run the kill block to kill the service
