"""
This sample demonstrates an implementation of the Lex Code Hook Interface.

The sample is based on the BookTrip example provided with the Amazon Lex
service, but in this instance the sample provides a backed for a bot that
is capable of capturing C-SAT scores and freeform feedback related to talks
given at conferences and events.

For instructions on how to set up and test this bot, as well as additional
samples, visit the Lex Getting Started documentation
http://docs.aws.amazon.com/lex/latest/dg/getting-started.html.

"""

import json
import datetime
import time
import os
import dateutil.parser
import logging
import boto3
import random


from aws_xray_sdk.core import patch_all
# patch boto3 for instrumentation and tracing via xray
patch_all()

# set up logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# collect environment variables
kinesisStreamName = os.environ['STREAM_NAME']
dynamodbTableName = os.environ['TABLE_NAME']


# --- Helper functions that build all of the responses ---

def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def elicit_slot_with_card(session_attributes, intent_name, slots, slot_to_elicit, message, response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'message': {
                'contentType': 'PlainText',
                'content': message
            },
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'responseCard': response_card
        }
    }


def build_options(sessions, start_from=0):
    options = []
    for i in range(start_from, len(sessions)):
        options.append({'text': sessions[i], 'value': sessions[i]})
    return options


def build_response_card(title, subtitle, options):
    return {
        'contentType': 'application/vnd.amazonaws.card.generic',
        'version': 1,
        'genericAttachments': [{
            'title': title,
            'subTitle': subtitle,
            'buttons': build_options(options)
        }]
    }


# confirm_intent is unused for now, but keep it becasue we want to allow easy
# submission of feedback and ratings for sessions that customers have done the
# other action for. See the booktrip sample for implementation example for this
def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    logger.debug('delegate session_attributes={} slots={}'.format(session_attributes, slots))
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


# --- Other Helper Functions ---

def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(float(n))
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None


def get_day_difference(later_date, earlier_date):
    later_datetime = dateutil.parser.parse(later_date).date()
    earlier_datetime = dateutil.parser.parse(earlier_date).date()
    return abs(later_datetime - earlier_datetime).days


def add_days(date, number_of_days):
    new_date = dateutil.parser.parse(date).date()
    new_date += datetime.timedelta(days=number_of_days)
    return new_date.strftime('%Y-%m-%d')


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


""" --- rating-bot specific validation and helper functions """


def isfuture_date(datetotest):
    today = datetime.date.today()
    datetotest = dateutil.parser.parse(datetotest).date()
    if datetotest > today:
        return True
    else:
        return False


def isvalid_sessionscore(scoretotest):
    if (scoretotest >= 1) & (scoretotest <= 5):
        return True
    else:
        return False


def isvalid_location(location):
    """
    TODO: move these external to the function and store them in a DynamoDB table
    """
    valid_locations = ['london', 'leeds', 'manchester', 'tel aviv', 'new york', 'san francisco', 'seattle', 'stockholm', 'dublin', 'helsinki', 'singapore','dummy']
    return location.lower() in valid_locations


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def within_30_days(datetotest):
    datetotest = dateutil.parser.parse(datetotest).date()
    thirtydaysago = datetime.date.today() - datetime.timedelta(days=30)
    if datetotest > thirtydaysago:
        return True
    else:
        return False


def isvalid_sessionComments(sessionComments):
    if sessionComments and len(sessionComments) > 4:
        return True
    else:
        return False


def safe_attribute(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """
    try:
        return func()
    except AttributeError:
        return None


# Collect sentiment score (Amazon Comprehend implementation)
def getComprehendSentimentResult(stringToAnalyze):
    comprehendClient = boto3.client('comprehend')
    comprehendClientResponse = comprehendClient.detect_sentiment(
        Text=stringToAnalyze,
        LanguageCode='en')
    del comprehendClientResponse['ResponseMetadata']
    print(comprehendClientResponse['SentimentScore'][comprehendClientResponse['Sentiment'].title()])
    comprehendClientResponse['Confidence'] = comprehendClientResponse['SentimentScore'][comprehendClientResponse['Sentiment'].title()]
    del comprehendClientResponse['SentimentScore']
    return comprehendClientResponse


def validate_rating(slots):
    logger.debug('Initating validation of rating')
    sessionId = try_ex(lambda: slots['SessionID'])
    sessionDate = try_ex(lambda: slots['SessionDate'])
    sessionLocation = try_ex(lambda: slots['SessionLocation'])
    sessionScore = safe_int(try_ex(lambda: slots['SessionScore']))

    if sessionLocation and not isvalid_location(sessionLocation):
        return build_validation_result(
            False,
            'SessionLocation',
            '{} is not a valid session location.  Which City did this event take place in?  Please can you try a different location?'.format(sessionLocation)
        )

    if sessionDate and not isvalid_date(sessionDate):
        return build_validation_result(
            False,
            'SessionDate',
            '{} isn\'t a valid date.  Please enter a date in day month year format, or month day year format if you prefer.'.format(sessionDate)
        )

    if (sessionScore or sessionScore == 0) and not isvalid_sessionscore(sessionScore):
        return build_validation_result(
            False,
            'SessionScore',
            '{} is not a valid session score.  Please enter a score between 1 and 5'.format(sessionScore)
        )

    if sessionDate and isfuture_date(sessionDate):
        return build_validation_result(
            False,
            'SessionDate',
            '{} is in the future.  Please enter a date in the past, or today\'s date'.format(sessionDate)
        )

    if sessionDate and not within_30_days(sessionDate):
        return build_validation_result(
            False,
            'SessionDate',
            '{} is more than 30 days ago and I only record for sessions in the last 30 days.  Please enter a more recent date or leave a rating more promptly next time.'.format(sessionDate)
        )

    return {'isValid': True}


def validate_feedback(slots):
    logger.debug('Initating validation of feedback')
    sessionId = try_ex(lambda: slots['SessionID'])
    sessionDate = try_ex(lambda: slots['SessionDate'])
    sessionLocation = try_ex(lambda: slots['SessionLocation'])
    sessionComments = try_ex(lambda: slots['SessionComments'])

    if sessionLocation and not isvalid_location(sessionLocation):
        return build_validation_result(
            False,
            'SessionLocation',
            '{} is not a valid session location.  Which City did this event take place in?  Please can you try a different location?'.format(sessionLocation)
        )

    if sessionDate and not isvalid_date(sessionDate):
        return build_validation_result(
            False,
            'SessionDate',
            '{} isn\'t a valid date.  Please enter a date in day month year format, or month day year format if you prefer.'.format(sessionDate)
        )

    if sessionDate and isfuture_date(sessionDate):
        return build_validation_result(
            False,
            'SessionDate',
            '{} is in the future.  Please enter a date in the past, or today\'s date'.format(sessionDate)
        )

    if sessionDate and not within_30_days(sessionDate):
        return build_validation_result(
            False,
            'SessionDate',
            '{} is more than 30 days ago and I only record feedback for sessions in the last 30 days.  Please enter a more recent date or leave your feedback more promptly next time.'.format(sessionDate)
        )

    # once we have everything else, prompt for feedback

    if (sessionId and sessionLocation and sessionDate) and not isvalid_sessionComments(sessionComments):
        return build_validation_result(
            False,
            'SessionComments',
            'I didn\'t get your feedback. What did you think of the session?'
        )

    return {'isValid': True}


def validate_testing(slots):
    logger.debug('Initating validation of testing with slots{}'.format(slots))
    TestTarget = try_ex(lambda: slots['TestTarget'])
    if TestTarget and TestTarget not in ["A", "B", "C"]:
        return build_validation_result(
            False,
            'TestTarget',
            '{} is not a valid test target.  Try A, B or C?'.format(TestTarget)
        )
    return {'isValid': True}


""" --- Functions that control the rating-bot bot's behavior --- """


def provide_feedback(intent_request):
    """
    Performs fulfillment for the ProvideFeedback intent.
    """

    logger.debug('provide_feedback intent_request={}'.format(intent_request))

    """
    DESIGN Q

    Two options on the sentiment analysis -
    First is to do that here, within the fulfilment function
    Second is to use another kinesis stream, and wrtie a second lambda function for the sentiment analysis so it's async

    ** for now we're doing it here because Amazon Comprehend doesn't introduce significant latency and it makes for a nice visualisation in Amazon X-Ray

    """

    sessionId = try_ex(lambda: intent_request['currentIntent']['slots']['SessionID'])
    sessionDate = try_ex(lambda: intent_request['currentIntent']['slots']['SessionDate'])
    sessionLocation = try_ex(lambda: intent_request['currentIntent']['slots']['SessionLocation'])
    sessionComments = try_ex(lambda: intent_request['currentIntent']['slots']['SessionComments'])
    userId = try_ex(lambda: intent_request['userId'])
    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # next bit of code is redundant, I think
    sessionFeedback = json.dumps({
        'RecordType': 'SessionFeedback',
        'UserId': userId,
        'Location': safe_attribute(lambda: sessionLocation.title()),
        'Date': sessionDate,
        'SessionComments': sessionComments,
        'ID': safe_attribute(lambda: sessionId.title())
    })
    # end redundant block

    session_attributes['currentFeedback'] = sessionFeedback

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_feedback(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots = intent_request['currentIntent']['slots']
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        session_attributes['currentFeedback'] = sessionFeedback
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # slots are all populated

    # get the sentiment score from Amazon Comprehend
    comprehendSentimentResult = getComprehendSentimentResult(sessionComments)

    # create a new sessionFeedback object containing all the slots, plus the sentiment score. This will be the payload for our Kinesis stream to Elasticsearch
    sessionFeedback = json.dumps({
        'RecordType': 'SessionFeedback',
        'UserId': userId,
        'Location': safe_attribute(lambda: sessionLocation.title()),
        'Date': sessionDate,
        'SessionComments': sessionComments,
        'comprehendSentimentResult': comprehendSentimentResult,
        'ID': safe_attribute(lambda: sessionId.title())
    })

    # Leave feedback on the session.  Write log mesage and rating object to Kinesis stream in this case.
    # write some debugging to let us know that we're doing this.

    logger.debug('Attempting to fulfill ProvideFeedback under={}'.format(sessionFeedback))

    # kinesisStreamName comes from the global which we populated with the environment variable
    kinesisClient = boto3.client('kinesis')
    putResponse = kinesisClient.put_record(StreamName=kinesisStreamName, Data=sessionFeedback, PartitionKey='partitionKey')

    logger.debug('Rating posted to stream response={}'.format(putResponse))

    try_ex(lambda: session_attributes.pop('currentFeedback'))
    session_attributes['lastConfirmedFeedback'] = sessionFeedback

    # return with a confirmation message.
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thank you for providing feedback on this session.'
        }
    )


def rate_session(intent_request):
    """
    Performs fulfillment for the RateSession intent.
    """

    logger.debug('rate_session intent_request={}'.format(intent_request))

    sessionId = try_ex(lambda: intent_request['currentIntent']['slots']['SessionID'])
    sessionDate = try_ex(lambda: intent_request['currentIntent']['slots']['SessionDate'])
    sessionLocation = try_ex(lambda: intent_request['currentIntent']['slots']['SessionLocation'])
    sessionScore = safe_int(try_ex(lambda: intent_request['currentIntent']['slots']['SessionScore']))
    userId = try_ex(lambda: intent_request['userId'])
    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    sessionRating = json.dumps({
        'RecordType': 'SessionRating',
        'UserId': userId,
        'Location': safe_attribute(lambda: sessionLocation.title()),
        'Date': sessionDate,
        'Score': sessionScore,
        'ID': safe_attribute(lambda: sessionId.title())
    })

    session_attributes['currentRating'] = sessionRating

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_rating(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots = intent_request['currentIntent']['slots']
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        session_attributes['currentRating'] = sessionRating
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # Slots are all populated.

    # Rate the session.  Write log mesage and rating object to Kinesis stream in this case.
    # first, write some debugging to let us know that we're doing this.
    logger.debug('Attempting to fulfill RateSession under={}'.format(sessionRating))

#   kinesisStreamName comes from the global which we populate from the environment variable
    kinesisClient = boto3.client('kinesis')
    putResponse = kinesisClient.put_record(StreamName=kinesisStreamName, Data=sessionRating, PartitionKey='partitionKey')

    logger.debug('Rating posted to stream response={}'.format(putResponse))

    try_ex(lambda: session_attributes.pop('currentRating'))
    session_attributes['lastConfirmedRating'] = sessionRating

    # return with a confirmation message
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thank you for rating this session.'
        }
    )


def thanks(intent_request):
    """
    Performs fulfillment for the HelpMe intent.
    """
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # populate a list with a few options for saying thanks!
    thanks_content_options = ['No problem!', 'You are very welcome.', 'Happy to help.', 'That\'s fine.', 'No. Thank you.', 'Any time.']

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': random.choice(thanks_content_options)
        }
    )


def cancel_request(intent_request):
    """
    Performs fulfillment for the HelpMe intent.
    """
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # popluate a list with a few options that we can use to respond to the cancel intent
    cancel_content_options = ['No problem. Let me know if I can help with anything else.', 'Let me know if you need anything else in future.', 'OK. Chat to you again soon.']

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': random.choice(cancel_content_options)
        }
    )


def testing(intent_request):
    """
    Performs fulfillment for the HelpMe intent.
    """
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    featureToTest = try_ex(lambda: intent_request['currentIntent']['slots']['TestTarget'])

    testingTarget = json.dumps({
        'TestTarget': featureToTest
    })

    """

    # populate list with a few options that we can use to respond to the testing intent
    testing_content_options = ['Try asking for help to see what I can help with.','I don\'t support testing via a chat session right now.']

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': random.choice(testing_content_options)
        }
    )

    """
    session_attributes['currentTest'] = testingTarget

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_testing(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots = intent_request['currentIntent']['slots']
            slots[validation_result['violatedSlot']] = None

            response = elicit_slot_with_card(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                "Select an option or type another option",
                build_response_card("title", "subtitle", ["A", "B", "C"])
            )

            logger.debug("elicit_slot_with_card generated : {}".format(json.dumps(response)))

            return response

        session_attributes['currentTest'] = testingTarget
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    try_ex(lambda: session_attributes.pop('currentTest'))
    session_attributes['lastConfirmedTest'] = testingTarget
    # return with a confirmation message

    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Fulfilling testing intent using with TestTarget: {}'.format(featureToTest)
        }
    )

# --- Intent router ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to the bot's intent handlers
    if intent_name == 'Testing':
        return testing(intent_request)
    if intent_name == 'CancelRequest':
        return cancel_request(intent_request)
    if intent_name == 'Thanks':
        return thanks(intent_request)
    if intent_name == 'RateSession':
        return rate_session(intent_request)
    elif intent_name == 'ProvideFeedback':
        return provide_feedback(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the Europe/London time zone.
    os.environ['TZ'] = 'Europe/London'
    time.tzset()

    logger.debug('event.bot.name={}'.format(event['bot']['name']))
    logger.debug('event={}'.format(event))

    response = dispatch(event)
    logger.debug('lambda_handler returning with response={}'.format(json.dumps(response)))

    return response
