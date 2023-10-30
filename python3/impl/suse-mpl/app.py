# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import pprint
import sys
import uuid

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import pubsub_v1

from impl.database.database import JsonDatabase

PROJECT_ID = os.environ['GOOGLE_CLOUD_PROJECT']
DEBUG = ('DEBUG_GOOGLE' in os.environ)

PUBSUB_SUBSCRIPTION = 'codelab'

PROCUREMENT_API = 'cloudcommerceprocurement'


def _generate_internal_account_id():
    ### TODO: Replace with whatever ID generation code already exists. ###
    if DEBUG:
        print('in _generate_internal_account_id')
    return str(uuid.uuid4())


class Procurement(object):
    """Utilities for interacting with the Procurement API."""

    def __init__(self, database):
        self.service = build(PROCUREMENT_API, 'v1', cache_discovery=False)
        self.database = database

    ##########################
    ### Account operations ###
    ##########################

    def _get_account_id(self, name):
        if DEBUG:
            print('in _get_account_id:name:' + name)
            print('in _get_account_id/procurementid:' + name[len('providers/DEMO-{}/accounts/'.format(PROJECT_ID)):])
        return name[len('providers/DEMO-{}/accounts/'.format(PROJECT_ID)):]

    def _get_account_name(self, account_id):
        if DEBUG:
            print('in _get_account_name:'+ 'providers/DEMO-{}/accounts/{}'.format(PROJECT_ID, account_id))
        return 'providers/DEMO-{}/accounts/{}'.format(PROJECT_ID,
                                                      account_id)

    def get_account(self, account_id):
        """Gets an account from the Procurement Service."""
        name = self._get_account_name(account_id)
        request = self.service.providers().accounts().get(name=name)
        if DEBUG:
            print('in _get_account:request:',end="")
            pprint.pprint(request)
        try:
            response = request.execute()
            return response
        except HttpError as err:
            if err.resp.status == 404:
                return None

    def approve_account(self, account_id):
        """Approves the account in the Procurement Service."""
        name = self._get_account_name(account_id)
        request = self.service.providers().accounts().approve(
            name=name, body={'approvalName': 'signup'})
        request.execute()

    def handle_account_message(self, message):
        """Handles incoming Pub/Sub messages about account resources."""

        if DEBUG:
            print('in handle_account_message')
        account_id = message['id']

        customer = self.database.read(account_id)
        account = self.get_account(account_id)

        ############################## IMPORTANT ##############################
        ### In true integrations, Pub/Sub messages for new accounts should  ###
        ### be ignored. Account approvals are granted as a one-off action   ###
        ### during customer sign up. This codelab does not include the sign ###
        ### up flow, so it chooses to approve accounts here instead.        ###
        ### Production code for real, non-codelab services should never     ###
        ### blindly approve these. The following should be done as a result ###
        ### of a user signing up.                                           ###
        #######################################################################
        if account:
            approval = None
            for account_approval in account['approvals']:
                if account_approval['name'] == 'signup':
                    approval = account_approval
                    break

            if approval:
                if approval['state'] == 'PENDING':
                    # See above note. Actual production integrations should not
                    # approve blindly when receiving a message.
                    self.approve_account(account_id)

                elif approval['state'] == 'APPROVED':
                    # Now that it's approved, store a record in the database.
                    internal_id = _generate_internal_account_id()
                    customer = {
                        'procurement_account_id': account_id,
                        'internal_account_id': internal_id,
                        'products': {}
                    }
                    self.database.write(account_id, customer)
            else:
                # The account has been deleted, so delete the database record.
                if customer:
                    self.database.delete(account_id)

        # Always ack account messages. We only care about the above scenarios.
        return True

    ##############################
    ### Entitlement operations ###
    ##############################

    def _get_entitlement_name(self, entitlement_id):
        if DEBUG:
            print('_get_entitlement_name:' + 'providers/DEMO-{}/entitlements/{}'.format(PROJECT_ID,entitlement_id))
        return 'providers/DEMO-{}/entitlements/{}'.format(PROJECT_ID,
                                                          entitlement_id)

    def get_entitlement(self, entitlement_id):
        """Gets an entitlement from the Procurement Service."""
        name = self._get_entitlement_name(entitlement_id)
        request = self.service.providers().entitlements().get(name=name)
        if DEBUG:
            print('get_entitlement:request:name:' + name)
            print('get_entitlement:request:entitlement_id:' + entitlement_id)
            print('get_entitlement:request:', end="")
            pprint.pprint(request)
            print()
        try:
            response = request.execute()
            return response
        except HttpError as err:
            if err.resp.status == 404:
                return None

    def approve_entitlement(self, entitlement_id):
        """Approves the entitlement in the Procurement Service."""
        name = self._get_entitlement_name(entitlement_id)
        request = self.service.providers().entitlements().approve(
            name=name, body={})
        request.execute()

    def approve_entitlement_plan_change(self, entitlement_id, new_pending_plan):
        """Approves the entitlement plan change in the Procurement Service."""
        name = self._get_entitlement_name(entitlement_id)
        body = {'pendingPlanName': new_pending_plan}
        request = self.service.providers().entitlements().approvePlanChange(
            name=name, body=body)
        request.execute()

    def handle_active_entitlement(self, entitlement, customer, account_id):
        """Updates the database to match the active entitlement."""
        product = {
            'product_id': entitlement['product'],
            'plan_id': entitlement['plan'],
            'start_time': entitlement['createTime'],
        }

        if 'usageReportingId' in entitlement:
            product['usageReportingId'] = entitlement['usageReportingId']

        customer['products'][entitlement['product']] = product

        ### TODO: Set up the service for the customer to use. ###
        self.database.write(account_id, customer)

    def handle_entitlement_message(self, message, event_type):
        """Handles incoming Pub/Sub messages about entitlement resources."""
        entitlement_id = message['id']

        entitlement = self.get_entitlement(entitlement_id)

        if DEBUG:
            print('handle_entitlement_message:entitlement_id:' + entitlement_id)
            print('handle_entitlement_message:entitlement:', end="")
            pprint.pprint(entitlement)
            print()
        if not entitlement:
            # Do nothing. The entitlement has to be canceled to be deleted, so
            # this has already been handled by a cancellation message.
            return True

        google_account_id = self._get_account_id(entitlement['account'])
        customer = self.database.read(google_account_id)
        state = entitlement['state']
        if DEBUG:
            print('google_account_id:' + google_account_id)
            print('customer:',end="")
            pprint.pprint(customer)
            print()

        if not customer:
            # If the record for this customer does not exist, don't ack the
            # message and wait until an account message is handled and a record
            # is created.
            # this case should not happed. account creation should always happen first.
            # if account event comes after this request, then handling this message requires
            # restarting the process
            return False

        if event_type == 'ENTITLEMENT_CREATION_REQUESTED':
            if state == 'ENTITLEMENT_ACTIVATION_REQUESTED':
                # Approve the entitlement and wait for another message for when
                # it becomes active before setting up the service for the
                # customer and updating our records.
                self.approve_entitlement(entitlement_id)
                return True
            elif state == 'ENTITLEMENT_ACTIVE':
                # means activate request already done
                # but message ack must have been dropped
                # nohing to do, just ack it.
                return True

        elif event_type == 'ENTITLEMENT_ACTIVE':
            if state == 'ENTITLEMENT_ACTIVE':
                # Handle an active entitlement by writing to the database.
                self.handle_active_entitlement(entitlement, customer,
                                               google_account_id)
                return True

        elif event_type == 'ENTITLEMENT_PLAN_CHANGE_REQUESTED':
            if state == 'ENTITLEMENT_PENDING_PLAN_CHANGE_APPROVAL':
                # Don't write anything to our database until the entitlement
                # becomes active within the Procurement Service.
                self.approve_entitlement_plan_change(
                    entitlement_id, entitlement['newPendingPlan'])
                return True

        elif event_type == 'ENTITLEMENT_PLAN_CHANGED':
            if state == 'ENTITLEMENT_ACTIVE':
                # Handle an active entitlement after a plan change.
                self.handle_active_entitlement(entitlement, customer,
                                               google_account_id)
                return True

        elif event_type == 'ENTITLEMENT_PLAN_CHANGE_CANCELLED':
            # Do nothing. We approved the original change, but we never recorded
            # it or changed the service level since it hadn't taken effect yet.
            return True

        elif event_type == 'ENTITLEMENT_CANCELLED':
            if state == 'ENTITLEMENT_CANCELLED':
                # Clear out our records of the customer's plan.
                if entitlement['product'] in customer['products']:
                    del customer['products'][entitlement['product']]

                    ### TODO: Turn off customer's service. ###
                    self.database.write(google_account_id, customer)
                return True

        elif event_type == 'ENTITLEMENT_PENDING_CANCELLATION':
            # Do nothing. We want to cancel once it's truly canceled. For now
            # it's just set to not renew at the end of the billing cycle.
            return True

        elif event_type == 'ENTITLEMENT_CANCELLATION_REVERTED':
            # Do nothing. The service was already active, but now it's set to
            # renew automatically at the end of the billing cycle.
            return True

        elif event_type == 'ENTITLEMENT_DELETED':
            # Do nothing. The entitlement has to be canceled to be deleted, so
            # this has already been handled by a cancellation message.
            return True

        return False


def main(argv):
    """Main entrypoint to the integration with the Procurement Service."""

    if len(argv) != 1:
        print('Usage: python3 -m impl.suse-mpl.app')
        return

    # Construct a service for the Partner Procurement API.
    database = JsonDatabase()
    procurement = Procurement(database)

    # Get the subscription object in order to perform actions on it.
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID,
                                                     PUBSUB_SUBSCRIPTION)

    def callback(message):
        """Callback for handling Cloud Pub/Sub messages."""
        payload = json.loads(message.data)

        print('callback:message:data', end="")
        pprint.pprint(payload)
        print()

        ack = False
        if 'entitlement' in payload:
            ack = procurement.handle_entitlement_message(payload['entitlement'],
                                                         payload['eventType'])
        elif 'account' in payload:
            ack = procurement.handle_account_message(payload['account'])
        else:
            # If there's no account or entitlement, then just ack and ignore the
            # message. This should never happen.
            ack = True

        # ideally all possiblities should have been handled above and
        # ack should always be set, but just in case we check.
        # in either case we ack, but want to not that we had an event we
        # could not handle.
        if ack:
            if DEBUG:
                print("acking message:" + payload['eventId'])
            message.ack()
        else:
            if DEBUG:
                print("no ack, but ack anyway" + payload['eventId'])
            message.ack()

    subscription = subscriber.subscribe(subscription_path, callback=callback)

    print('Listening for messages on {}'.format(subscription_path))
    print('Exit with Ctrl-\\')

    while True:
        try:
            subscription.result()
        except Exception as exception:
            print('Listening for messages on {} threw an Exception: {}.'.format(
                subscription_path, exception))


if __name__ == '__main__':
    main(sys.argv)
