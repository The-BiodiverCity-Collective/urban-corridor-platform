# Overview

This repository contains the source code of the Urban Corridor Platform. This platform is built to provide cities with a way to educate and involve civil society groups, individuals and other interested parties with tools to collaboratively build urban, green corridors.

The following technologies are used:

- Django 5
- Python 3
- PostgreSQL/PostGIS
- Docker
- NodeJS
- TailwindCSS

In order to meaningfully contribute to this project (or clone it and use it for your own purposes), you should ideally be comfortable with (or willing to learn about) the aforementioned technologies. You can make a meaningful contribution if you know either about python/Django, or about HTML/CSS/Javascript (allowing you to contribute with back-end or front-end programming, respectively).

# Getting started

DISCLAIMER: the system is currently running in a Linux environment only, but it should also work perfectly fine on Windows or other operating systems if you have Docker running on it. The commands shown below, however, are Linux specific, but these are simply copy / create directory commands that should be easy enough in any OS.

To get started with this project, do the following:

- Clone the repository on your local machine
- Install Docker and specifically [Docker Compose](https://docs.docker.com/compose/)
- Create a number of baseline directories (see below)
- Create a configuration file (see below)
- Build your container
- Import our database

Once this is done, you have completed all the required steps to get the system running. Specific details below:

Let's say you have cloned this repository to /home/user/ucp

    $ cd /home/user/ucp
    $ mkdir src/{media,logs,static}
    $ cp src/ie/settings.sample.py src/ie/settings.py
    $ sudo docker-compose build

Now that this is done, you can run the container like so:

    $ cd /home/user/ucp
    $ sudo docker-compose up

Wait a few moments, and the containers should be up and running. Your main container (ucp_web) will display errors because there is no database yet. Please select your preferred database below and import this as follows:

    $ sudo docker container exec -i ucp_db psql -U postgres ucp < db.sql

Replace "db.sql" for the name of your database file (which should be uncompressed before loading it). After the database is loaded, you will need to reload your container (CTRL+C followed by:

    $ sudo docker-compose up

And the website should be up and running at [http://0.0.0.0:7777](http://0.0.0.0:7777) and adminer to manage the database is available at [http://0.0.0.0:8080](http://0.0.0.0:8080).

NOTE: there may be additional database migrations that are not yet applied to this database. You can run the migrations by running:

    $ ./migrate

From the root directory of the project. This is a shortcut to migrate any unapplied migrations in the docker container (check out the file contents to see what commands it runs).

# CSS

This repository uses TailwindCSS (https://tailwindcss.com/). In general terms, here is how this works:

- There is a node package installed (note that Node is included in the Dockerfile), called `tailwindcss`. Also included are `postcss-cli`, `postcss` and `autoprefixer`. These packages all work together to get the CSS properly set up. See more at: https://tailwindcss.com/docs/installation/tailwind-cli
- Have a look at `package.json` for which files exactly are included. 
- Tailwind includes a ton of predefined styles. However, only the styles that are actually used on the website are included in the CSS file. This is done by running a script that checks which files are used and that then creates the static CSS file corresponding to those styles. 
- Run `csscreate` to re-generate the CSS file. The configuration of what file is created is included in the `package.json` file. At present, `output.css` is the name of the final CSS. There is an intermediate CSS called `ucp.css` that includes details on which Tailwind features to load, AND it includes additional CSS to embed in `output.css`
