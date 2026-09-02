All data files are located in the ${ASSETS_PATH} directory. The data files are in JSON format and follow a specific schema. Below is a description of the data schema for each file. The environment variables are defined in the .env file located in the root directory of the project. Check .env.example for the list of all environment variables and their default values. The data files are used to populate the content of the website and can be edited to change the content. The data files are loaded into the application at runtime and can be accessed via the API endpoints. The data files are also used to generate static pages for the website. 

Below are sections describing the data schema for each data file. The json examples contain value descriptions in the form of <value description>. The asterisk (*) <value description*> indicates that the value is required. 

#Recommendations (or recs)
Represent collections of books for a single recommendation. Stored in a single file ${RECS_PATH} as a list of json objects:
```
{
  "recs": [
    {
      "rec": "<Name of the recommendation*>",
      "books": [
        {
          "title": "<Title of the book*>",
          "description": "<Description of the book>",
          "authors": [
            "<Name of the author>",
            ...
          ],
          "soldBy": [
            "<Name of the seller>",
            ...
          ]
        }
      ],
      "emoji": "<Emoji representing the recommendation>"
    },
    ...
  ]
}
```

#Timetable
Represent a list of events for a single day. Stored in multiple files ${TIMETABLE_PATH} as a list of json objects. Each file represents a single day and is named in the format DDMMYYYY.json:
```
{
  "date": "<Date in format DDMMYYYY*>",
  "events": [
    {
      "time": "<Time of the start of the event in format HH:MM in 24-hour format*>",
      "title": "<Title of the event*>",
      "description": "<Description of the event>",
      "participants": [<Participant name>,...],
      "organizer": "<Name of the organizer>",
      "location": "<Location of the event>",
      "is_children_activity": <boolean true/false indicating if the event is suitable for children*>
    },
    ...
  ]
}
```

#Participants
Represent a list of participants for the event. Stored in a single file ${PARTICIPANTS_PATH} as a list of json objects:
```
{
  "participants": [
    {
      "name": "<Name of the participant*>",
      "stand": "<Stand number of the participant, can be alphanumeric*>",
      "description": "<Description of the participant>",{PARTICIPANTS_PATH}/logos directory>",
      "link": "<Link to the participant's website or social media page>"
    },
    ...
  ]
}
```
