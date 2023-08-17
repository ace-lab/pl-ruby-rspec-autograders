FROM ruby:2.6-alpine3.14

RUN apk update 
RUN apk upgrade
RUN apk add bash ruby-dev
RUN apk add --no-cache python3

RUN apk add --no-cache ruby ruby-bundler build-base

RUN gem install json rspec rake
RUN gem update --system 2.7.10
RUN gem install bundler -v 2.3.26

RUN mkdir /grader
COPY grader /grader
RUN chmod +x /grader/run.py

CMD sh
