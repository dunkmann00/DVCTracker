![DVC Tracker](https://www.georgeh2os.com/DVCTracker/static/images/dvctracker-logo-1.png "DVC Tracker Logo")

### Track DVC Specials and get notified of changes as they happen.

---

The description says it all. DVC Tracker will allow you to track DVC specials that are posted on 3rd party DVC Rental sites. This will enable you to find the perfect special for your next vacation or to keep track of all the changes that are happening. DVC Tracker will scrape the website and track everything it finds, comparing it to the data it has stored from previous runs. Any additions, removals, or changes in price to any of the specials, will be sent to you via an email. You can also configure DVC Tracker to send a text or a push notification when an important special has been either added or updated.

Currently, the only parser that is included in the repo is for [https://dvcrentalstore.com](https://dvcrentalstore.com).

Criteria
--------

DVC Tracker can be used to check for specials that are 'important'. These important specials will be emphasized in emails and will also trigger a text message/push notification when they are found. If you are **ONLY** interested in getting notified about important specials (rather than all specials) DVC Tracker can also be setup to send emails which only show the important specials. All of this is done through the `/criteria` view form.

The following criteria can be used to determine **'important'** status:
- Date
- Length of Stay
- Total Price
- Price/Night
- Points
- Price/Point
- Resort
- Room Type
- Room View

One group of criteria will only match a special if all of the criterion that are used match. You can use multiple groups (selecting the plus button on the form to add a group) to match for either set of criteria.

Running
-------

This app is a Flask app. There are several cli commands that are available, below are a few of the more important.

| Command          | Description       |
| ---------------- | ----------------- |
| `deploy` | Update your db schema to what is current in the project, add/update all of the static data into the db, and run an update for the latest specials.|
| <code>make&#x2011;new&#x2011;user</code> | Create new user. This protects all endpoints and is needed to manage the important criteria.|
| <code>update&#x2011;specials</code> | Triggers an update of all specials, and the sending of any necessary notifications (emails, text messages, push notifications).|

For more info on these commands and to see other available commands run `flask --help`.

This app also has a few views that are used to interact with it. While the core concept of this is to send emails with the updated specials, you can also check out all of the current specials and setup your account's contact info through the app's views.

| View             | Description       |  
| ---------------- | ----------------- |
| `/specials` | List of all the specials since the last time <code>update&#x2011;specials</code> was run.|
| `/specials/important` | List of all the important specials since the last time <code>update&#x2011;specials</code> was run.|
| `/specials/errors` | List of all specials that could not be successfully parsed.|
| `/criteria` | The criteria form is where you enter your preferences for **'important'** specials.|
| `/user` | The user form is where you enter your contact info. This includes any email addresses and phone numbers.|

There are a few other views that are used internally or for testing/development, but these are the ones that are needed to interact with DVC Tracker.

The main way that these are meant to be viewed is with the DVC Tracker iOS app. The app hides all of the details of the view addresses, authenticating, and is what enables push notifications. The source code for this is not currently available, but it is my plan to release that on Github as well.

### Other Components

There are several other pieces to DVC Tracker. First and foremost you need to hook it up to a database. PostgreSQL is what I have used, but the database code is mostly generic. When using SQLAlchemy and Alembic I tried to keep everything general and not Postgres specific. So no guarantees, but certainly most of it should work fine with other databases.

Below is a list of other services that are used. This has changed over time and may continue to do so.

| Feature      | Service |
| ------------ | ------- |
| Email        | [Mailgun](https://www.mailgun.com/) |
| Text Message | [Twilio](https://www.twilio.com/messaging/sms)  |
| APNs         | Handled ourselves with [PyAPNs2](https://github.com/Pr0Ger/PyAPNs2) |

Currently, there is only one service per feature. If more services are added it may make sense to provide different options for a particular feature. So for example, Twilio or some other texting service could be used to send text messages, depending on your preference.

Support
-------

This is in no way connected to Disney or DVC Rental Store. I originally made this just for myself when I was looking to visit Disney and hoping to find a good special. Over time I improved it and now think it can be useful to others as well! But if you feel it is lacking then it probably is. It currently allows me to run the tracker exactly how I need to, but if others find different ways that are better suited for them, I would love to extend DVC Tracker's capabilities. Hopefully we can continue to improve it together to make it even more useful for all!

If you have any ideas or find any bugs please submit an issue or pull request and I will look it over.
