import datetime
import json


class BugReportMessage:
    # Fields and constructor keywords match the existing Service Bus message schema.
    # pylint: disable=invalid-name,too-many-instance-attributes,too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        UserName,
        UserEmail,
        UserOrganization,
        PortalLanguage,
        PreferredLanguage,
        Timezone,
        Workspaces,
        Topics,
        URL,
        UserAgent,
        Resolution,
        LocalStorage,
        BugReportType,
        Description,
    ):
        self.UserName = UserName
        self.UserEmail = UserEmail
        self.UserOrganization = UserOrganization
        self.PortalLanguage = PortalLanguage
        self.PreferredLanguage = PreferredLanguage
        self.Timezone = Timezone
        self.Workspaces = Workspaces
        self.Topics = Topics
        self.URL = URL
        self.UserAgent = UserAgent
        self.Resolution = Resolution
        self.LocalStorage = LocalStorage
        self.BugReportType = BugReportType
        self.Description = Description

    def to_json(self):
        def json_default(value):
            if isinstance(value, datetime.date):
                return {"year": value.year, "month": value.month, "day": value.day}
            return value.__dict__

        return json.dumps(self, default=json_default, sort_keys=True, indent=4)


# pylint: enable=invalid-name,too-many-instance-attributes,too-many-arguments,too-many-positional-arguments
