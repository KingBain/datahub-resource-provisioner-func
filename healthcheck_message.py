import datetime
import json


class HealthcheckMessage:
    # Serialized property names and constructor names are part of the message contract.
    # pylint: disable=invalid-name,too-many-positional-arguments
    # 5 = Undefined; 2 - Healthy; 4 - Unhealthy
    STATUS_HEALTHY = 2
    STATUS_UNHEALTHY = 4
    STATUS_UNDEFINED = 5

    TYPE_WORKSPACE_SYNC = 8
    TYPE_DATABRICKS_SYNC = 9

    def __init__(self, Type, Group, Name, Details=None, Status=None):
        self.ResourceType = Type
        self.Group = Group
        self.Name = Name
        self.Status = Status or self.STATUS_UNDEFINED
        self.Details = Details
        self.HealthCheckTimeUtc = datetime.datetime.now(datetime.UTC)

    def to_json(self):
        def json_default(value):
            if isinstance(value, datetime.date):
                return {"year": value.year, "month": value.month, "day": value.day}
            return value.__dict__

        return json.dumps(self, default=json_default, sort_keys=True, indent=4)


# pylint: enable=invalid-name,too-many-positional-arguments
