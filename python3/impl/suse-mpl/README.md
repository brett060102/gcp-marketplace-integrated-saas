Processing loop for SUSE Multi Pruduct Listings.

Main:
        READ events from subscription. Any pending events are handled in order
        when all handled wait for more.

        For each event, invoke  subscription handler callback with event message/payload.


callback (message)
         to general types of message acount and entitlement

         for account events invoke handle_account_message

         for entitlement invoke handle_entitlement_message

         each handler reurns boolean, that determines if event was proccessed.

         acknowlege message to remove it from queue.

handle_account_message( event message )
        gets account id from message, this is the google procurement ID.
        uses  get_account which _get_account_name to contruct request to validate that account exists

        if google has record account, loop over approvals, looking for "signup", set approval and break out.
        if approval set, then found account to be signed up.
             if state "PENDING", meaning sign up requested, but not approved, then approve it signup request
             if state "APPROVED", meaning sign up has been approved
                get/create SUSE ID (internal_account_id) for account
                write cust record to database, it includes procurement_account_id, internal_account_id, and empty products
            if not above, then assume google account was deleted, so delete record from database.

handle_entitlement_message(event message/payload, event_type)
       get entitlement_id from message
       use get_entitlement(entitlement_id) to get the entitlement
       if entitlement record does not exists, then request was either cancelled or deleted, just return true so message is acked.
       get google_account_id/procurementid using _get_account_id
       get customer reccord from DB via  google_account_id from above.
       if no customer reccord; return false. this should not happen and I think needs to be thought about.
       if event_type == 'ENTITLEMENT_CREATION_REQUESTED && state == ENTITLEMENT_ACTIVATION_REQUESTED; approve and return true
       if event_type == 'ENTITLEMENT_CREATION_REQUESTED && state == ENTITLEMENT_ACTIVE; return true has already been approved.
       if event_type == 'ENTITLEMENT_ACTIVE' && state == 'ENTITLEMENT_ACTIVE'; handle_active_entitlement
       handle_active_entitlement
           update DB to record product, including usageReportingId if present.
       if event_type == ''ENTITLEMENT_PLAN_CHANGE_REQUESTED` && state == 'ENTITLEMENT_PENDING_PLAN_CHANGE_APPROVAL; approve_entitlement_plan_change
       approve_entitlement_plan_change
           tell google plan change approved.
       if event_type == 'ENTITLEMENT_PLAN_CHANGED' &&  state == 'ENTITLEMENT_ACTIVE; handle_active_entitlement to update DB with new plan info
       if event_type == 'ENTITLEMENT_PLAN_CHANGE_CANCELLED'; do nothing and ack (return True)
       if event_type == 'ENTITLEMENT_CANCELLED && state == 'ENTITLEMENT_CANCELLED'; remove plan info from DB
       if event_type == 'ENTITLEMENT_PENDING_CANCELLATION'; do nothing and ack (return True)
       if event_type == 'ENTITLEMENT_DELETED'; do nothing and ack (return True)
       if no above apply, then return false meaning something came through we did no know how to handle

utilities:
 _get_account_id: (self, name)
    extracts google procurementid from via name[len('providers/DEMO-{}/accounts/'.format(PROJECT_ID)):]


_get_account_name (self, account_id)
    gets the via:  providers/DEMO-{}/accounts/{}'.format(PROJECT_ID, account_id)
    only seem to get used in handling account creation, which only occus once per user account.

get_account: t(self, account_id)
    gets account info via https request to google


approve_account(self, account_id)
   approves account via https request to google

_get_entitlement_name(self, entitlement_id)
  gets entitlement name via providers/DEMO-{}/entitlements/{}'.format(PROJECT_ID,entitlement_id)

get_entitlement(self, entitlement_id)
   gets entitlement via https request back to google

 approve_entitlement(self, entitlement_id)
   approves entitlement request via https request back to google

approve_entitlement_plan_change(self, entitlement_id, new_pending_plan)
  approves user request to change plan request via https request back to google.
  should not apply to use since we only have one plan for users.

handle_active_entitlement(self, entitlement, customer, account_id)
  records active entitlement into DB
