# -*- coding: utf-8 -*-
#
#    Django error tracker middleware responsible for recording exception
#
#    :copyright: 2020 Sonu Kumar
#    :license: BSD-3-Clause
#

from error_tracker.django import get_masking_module, get_context_builder, get_ticketing_module, \
    get_exception_model, get_notification_module, APP_ERROR_SUBJECT_PREFIX, APP_ERROR_EMAIL_SENDER, \
    APP_ERROR_RECIPIENT_EMAIL, TRACK_ALL_EXCEPTIONS, APP_ERROR_NOTIFICATION_ONCE, \
    APP_ERROR_TICKET_ONCE
from error_tracker.libs.utils import get_exception_name, get_context_detail, get_notification_subject

model = get_exception_model()
ticketing = get_ticketing_module()
masking = get_masking_module()
notifier = get_notification_module()
context_builder = get_context_builder()


# noinspection PyMethodMayBeStatic
class ErrorTracker(object):
    """
     ErrorTracker class, this is responsible for capturing exceptions and
     sending notifications and taking other actions,
    """

    @staticmethod
    def _send_notification(request, message, exception, error):
        """
        Send notification to the list of entities or call the specific methods
        :param request: request object
        :param message: message having frame details
        :param exception: exception that's triggered
        :param error:  error model object
        :return: None
        """
        if notifier is None:
            return
        if request is not None:
            method = request.method
            url = request.get_full_path()
        else:
            method = ""
            url = ""
        subject = get_notification_subject(APP_ERROR_SUBJECT_PREFIX,
                                           method, url, exception)
        notifier.notify(request,
                        error,
                        email_subject=subject,
                        email_body=message,
                        from_email=APP_ERROR_EMAIL_SENDER,
                        recipient_list=APP_ERROR_RECIPIENT_EMAIL)

    @staticmethod
    def _raise_ticket(request, error):
        if ticketing is None:
            return
        ticketing.raise_ticket(request, error)

    @staticmethod
    def _post_process(request, frame_str, frames, error):
        message = f'URL: {request.path}' + '\n\n' if request is not None else ""
        message += frame_str
        send_notification = APP_ERROR_NOTIFICATION_ONCE is not True or error.notification_sent is not True
        raise_ticket = APP_ERROR_TICKET_ONCE is not True or error.ticket_raised is not True
        if send_notification:
            ErrorTracker._send_notification(request, message, frames[-1][:-1], error)
        if raise_ticket:
            ErrorTracker._raise_ticket(request, error)

    def capture_exception(self, request=None, exception=None, additional_context=None):
        """
        Record the exception details and do post processing actions. this method can be used to track any exceptions,
        even those are being excepted using try/except block.
        :param request:  request object
        :param exception: what type of exception has occurred
        :param additional_context: any additional context
        :return:  None
        """
        if request is not None:
            path = request.path
            host = request.META.get('HTTP_HOST', '')
            method = request.method
        else:
            path = ""
            host = ""
            method = ""

        ty, frames, frame_str, traceback_str, rhash, request_data = \
            get_context_detail(request, masking, context_builder,
                               additional_context=additional_context)
        error = model.create_or_update_entity(rhash=rhash, host=host, path=path, method=method,
                                              request_data=str(request_data),
                                              exception_name=get_exception_name(ty),
                                              exception_text=str(exception.args),
                                              traceback=traceback_str)
        ErrorTracker._post_process(request, frame_str, frames, error)


class ExceptionTrackerMiddleWare(ErrorTracker):
    """
    Error tracker middleware that's invoked in the case of exception occurs,
    this should be placed at the end of Middleware lists
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if exception is None and not TRACK_ALL_EXCEPTIONS:
            return
        self.capture_exception(request, exception)


# use this object to track errors in the case of custom failures, where try/except is used
error_tracker = ErrorTracker()
