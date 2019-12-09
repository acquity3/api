# Developer's Guide
This document describes the structure of the code, as well as any technologies
used in this application.

## High-level Design
Database Diagram: https://dbdiagram.io/d/5d986b51ff5115114db4ef22
API documentation: https://app.swaggerhub.com/apis-docs/acquity/Acquity/1.0.0-oas3

## General Structure
Here, we describe the files in the code base one by one, from the lowest level
to the highest level.

### Infrastructure and General Stuff

#### config.py
Contains configuration for the entire app:
- web settings, such as the host, the port, and CORS settings;
- database URL;
- email settings for Mailgun;
- job scheduler settings for apscheduler;
- Acquity-specific configuration, such as how long a round lasts.

Almost every file depends on this file.

#### database.py
Contains database models and infrastructure. This is built using SQLAlchemy.
Please see the SQLAlchemy documentation to understand this file better.

#### seeds.py
Contains function to seed the database. Is run on `./run_seeds.sh`.

#### email_service.py
Contains infrastructure to send emails. We use Mailgun for sending emails. It
also contains a dictionary for the email templates used.

#### exceptions.py
Contains general Acquity-specific exceptions.

#### scheduler.py
Contains code for the job scheduler. This is needed to e.g. run matching
algorithm when the round ends. We use the `apscheduler` library for this.

#### schemata.py
Contains infrastructure to validate input sent to the functions in
`services.py` file. Basically, request data sent through the controllers are
passed into these schema first. We validate the input using the library
`cerberus`. If there are validation errors, this function automates sending a
HTTP 422 with relevant information.

#### utils.py
Contains functions for miscellaneous purposes.

### Domain Logic

#### match.py
Contains the matching algorithm. The algorithm depends on the `networkx`
library, which is a library for general graph stuff. In particular, we use
`networkx` for its
[Hungarian Algorithm](https://en.wikipedia.org/wiki/Hungarian_algorithm)
implementation, which is an algorithm to do maximal matching with constraints.

#### services.py
Contains the main domain logic of this application. Basically the meat of this
whole application.

### Controllers

#### api.py
Bridges to HTTP. Basically, requests that come in just get passed directly to
the relevant functions in the `services.py` file, and the return value is
passed directly as a JSON response.

#### chat_service.py
Bridges to the websocket API. Similar to `api.py`, only that this is specific
to the chat stuff, and we use `socket.io` for the websocket stuff.

#### app.py
Wraps the entire app together into a Sanic instance and starts it.

## Tests
The main logic of this application resides in services.py, and that is the file
that is most tested. We created a very crude fixtures library as well in
`tests/fixtures.py`, in the style of the
[factory_bot](https://github.com/thoughtbot/factory_bot) Ruby gem.

We do not test `api.py` and `chat_service.py` since there is no complex logic
on these files. They are better tested with integration tests instead.

## Adding new logic
1. Write your brand new behavior in a function in the relevant class in
   `services.py`.
2. Test it in `tests/services/test_*.py`.
3. Validate the function arguments with the `@validate_input` decorator in
   `schemata.py`. Create the relevant schema in that file as well.
4. Write the "hollow controller" in `api.py` or `chat_service.py`.
