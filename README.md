Welcome to Rating-Bot, an Amazon Lex Chatbot Demo
=================================================

This sample code helps get you started with a Python backend for an Amazon Lex Chatbot.
This bot collects feedback scores and feedback comments from conference talks and stores them in an Elasticsearch cluster for visualisation via Kibana.

AWS Services that are used:

 - [Amazon Lex](https://aws.amazon.com/lex/)
 - [AWS Lambda](https://aws.amazon.com/lambda/)
 - [AWS X-Ray](https://aws.amazon.com/xray/)
 - [Amazon Comprehend](https://aws.amazon.com/xray/)
 - [Amazon Kinesis Data Streams](https://aws.amazon.com/kinesis/data-streams/)
 - [Amazon Kinesis Data Firehose](https://aws.amazon.com/kinesis/data-firehose/)
 - [Amazon Elasticsearch](https://aws.amazon.com/elasticsearch-service/)

What's Here
-----------

This sample was built from the AWS CodeStart CI/CD environment and contains the following files:

* README.md - this file
* buildspec.yml - this file is used by AWS CodeBuild to package your application for deployment to AWS Lambda
* index.py - this file contains the sample Python code for the Amazon Lex Validation & Fulfillment function 
* template.yml - this file contains the Serverless Application Model (SAM) and CloudFormation resources used by AWS Cloudformation to deploy your application to AWS Lambda and creat the other resources required for this application.
* requirements.txt - Python dependency management (used by AWS CodeBuild)


Getting Started
---------------

1. Create a blank python webservice codestar project
1. Replace contents of project with this project
1. Figure out all the bugs


What Do I Do Next?
------------------

Learn more about Amazon Lex and how to works here:
https://aws.amazon.com/lex

Learn more about Serverless Application Model (SAM) and how it works here:
https://github.com/awslabs/serverless-application-model/blob/master/HOWTO.md

AWS Lambda Developer Guide:
http://docs.aws.amazon.com/lambda/latest/dg/deploying-lambda-apps.html

Learn more about AWS CodeStar by reading the user guide, and post questions and
comments about AWS CodeStar on our forum.

AWS CodeStar User Guide:
http://docs.aws.amazon.com/codestar/latest/userguide/welcome.html

AWS CodeStar Forum: https://forums.aws.amazon.com/forum.jspa?forumID=248
