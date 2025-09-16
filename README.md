I want to build a command-line program that monitors the public disclosure system for U.S. Congressional stock trades. Members of Congress and the Senate are legally required to file periodic transaction reports when they or their immediate families buy or sell stocks.

The service should automatically check whenever new disclosure forms are filed and generate a report of recent trades from the last day. The report should include the name of the legislator, the company traded, the type of transaction (buy/sell), the dollar range, and a link to the full disclosure.

To start, I want the monitoring focused on specific legislators known for active trading: Nancy Pelosi, David Rouzer, Debbie Wasserman Schultz, and Ron Wyden. Later, it should be easy to add or remove names from the watch list.

The program should be executable directly from my Mac command line. It should be designed so I can schedule it to run automatically with a cron job once or twice a day. Each run should drop a text or CSV file on my Desktop containing the report of trades from the last 24 hours
