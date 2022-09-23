# DVC Tracker
Track DVC Specials and get notified of changes as they happen.

***This needs to be updated. Much of the configuration information is out of date. The `criteria.toml` file is no longer used and details on running the app could use a refresh as well. I plan to update this in the near future!***

---

The description says it all. DVC Tracker will allow you to track the specials that are posted on https://dvcrentalstore.com/. This will enable you to find the perfect special for your next vacation or to keep track of all the changes that are happening. DVC Tracker will scrape the website and track everything it finds, comparing it to the data it has stored from previous runs. Any additions, removals, or changes in price to any of the specials, will be sent to you via an email. You can also configure DVC Tracker to send a text when an important special has been either added or updated.

Configuration
-------------

DVC Tracker can be configured to check for specials that are 'important'. These important specials will be highlighted green in emails and will also trigger a text message when they are found. If you are **ONLY** interested in getting notified about important specials (rather than all specials) DVC Tracker can also be configured to send emails which only show the important specials. All of this is done through the [`criteria.toml`](criteria.toml) file.

Criteria File
-------------

The [`criteria.toml`](criteria.toml) file uses [TOML](https://github.com/toml-lang/toml) which is a configuration file format that is both easy for humans to read and manipulate as well as computers. This makes it well suited to be used by DVC Tracker for indicating important specials. The current criteria file includes examples of how you would indicate important specials so be sure to check that.

The structure for the criteria file is as follows:
+ If the `important_only` key is present and set to True, only important specials will be included in emails. The default is False.
+ Each set of criteria should be added to either the `[[preconfirm]]` or the `[[disc_points]]` Array Table.
+ You can have multiple sets of criteria by simply adding multiple items to the Array Table of the corresponding special type.

The following criteria can be used to determine 'important' status:
+ Date
+ Length of Stay
+ Total Price
+ Price/Night
+ Points
+ Resort
+ Room Type

Looking at an excerpt from the `criteria.toml` file we can see this in action:

```toml
important_only = false

[[preconfirm]]
  date.start = 2019-02-01
  date.end = 2019-02-25
  price_per_night = 400
  rooms = [
    "1-Bedroom",  #Note that rooms is a list and can have
    "Studio"      #more than one room type listed
  ]

...
```

Here we can see that `important_only` is set to False, thus changes to any specials will trigger an email. Next we see one set of criteria for preconfirmed specials. In this example, any special that overlaps Feb. 1, 2019 - Feb. 25, 2019, has a price/night that is equal to or less than $400, and is either a 1-Bedroom or a Studio will be considered an important special. All of these criteria must be met in order for a special to satisfy being important. Now let’s suppose you also wanted another set of criteria to be considered special. Looking at more of the `criteria.toml` we can see how to accomlish this:

```toml
important_only = false

[[preconfirm]]
  date.start = 2019-02-01        #Start date AND
  date.end = 2019-02-25          #End date AND
  price_per_night = 400          #Price/night AND
  rooms = [                      #Any of the listed Rooms
    "1-Bedroom",
    "Studio"
  ]

[[preconfirm]]                   #OR
  resorts = [                    #Any of the listed Resorts
    "Wilderness Lodge",
  ]

...
```

By adding another entry to the preconfirm array table, we have told DVC Tracker that if any of the specials are for the Wilderness Lodge they too are considered special. I think an easy way to look at it is that if you were talking to someone about the criteria, anything that is in the same array table item would be joined by *'and'* (i.e. price/night less than or equal to $400 *'and'* a 1-Bedroom or a Studio) whereas separate items would be joined by *'or'* (i.e. price/night less than or equal to $400... *'or'* at the Wilderness Lodge).

You may have also noticed that some criteria like the rooms and the resorts are arrays themselves. For these two criteria you can list multiple items right within the list. Another point worth noting is for dates. Dates are represented with a 4 digit year, followed by a 2 digit month, followed by a 2 digit day, all separated with a dash (i.e. `2019-02-25`). Also, if you are specifying dates for preconfirms you must include both a check-in (`date.start`) and check-out (`date.end`) date. But for discounted points, you just need the one date (`date`).

Running
-------

This app is setup as a Flask app. After you have setup your database, you just need to run the command `flask update-specials` in a cli. This will trigger the web scraping and then compare the new data from the DVC Rental Store site with what is stored in your database.

You could certainly run this app from your local machine. However, there is a `Procfile` included in the repo as I currently run this app on Heroku. I have found this to be very convenient. Doing this I can run the app on a regular interval and also get access to Heroku's add-on ecosystem, which is how I run the emails and text messages. The addons used are Postgres, Scheduler, Mailgun, & Till. This app, not being particularly burdensome, should allow you to stay within the free tier for Heroku and each addon, assuming you are not already using up your free tier hours.

I've also included both a `Pipfile` and a `requirements.txt` file so you can use either [Pipenv](https://pipenv.readthedocs.io/en/latest/) or Pip to configure your python environment and install dependencies. If you haven't heard of Pipenv I would recommend you check it out. I find it very useful in handling the repetitive task of managing a virtual environment, while also managing dependencies in a way that is somewhat more capable than Pip. But if that is not something you are interested in fear not, the requirements.txt should work just fine.

As this app is a Flask app, there are two routes that exist, `/specials` and `/specials/important`. In case it isn't already obvious what these do, the first returns a webpage that shows all of the specials and the second just shows the important specials. If access to these endpoints is not something you want then just ignore them. However, if you do want this functionality I would again recommend using Heroku as it is an easy way to ensure you can access your DVC Tracker instance from anywhere without much setup.

Support
-------

This is in no way connected to Disney or DVC Rental Store. I originally made this just for myself when I was looking to visit Disney and hoping to find a good special. Over time I improved it and now think it can be useful to others as well! But if you feel it is lacking then it probably is. It currently allows me to run the tracker exactly how I need to, but if others find different ways that are better suited for them, I would love to extend DVC Tracker's capabilities. Hopefully we can continue to improve it together to make it even more useful for all!

If you have any ideas or find any bugs please submit an issue or pull request and I will look it over.
