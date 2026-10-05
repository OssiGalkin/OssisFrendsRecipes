# Finding and Using Existing Tasks

Always prefer an existing official Task over a Code Task with hand-rolled logic, and a Code Task over a Custom Task.

**Practitioner heuristic — a working opinion, not from the docs:** experienced Frends developers typically reach for standard protocol Tasks directly — HTTP, SQL, SFTP, AMQP — rather than system-specific wrappers. Protocol Tasks need no Frends-specific knowledge to debug or extend and give full control over the call. Use system-specific Tasks (SAP, Salesforce, ServiceNow, …) when the target system carries real domain complexity that would otherwise need specialist knowledge to implement correctly.

## Where Task documentation lives

1. **Primary: `https://docs.frends.com/tasks/`** — the Tasks section of the main docs. Layout: `https://docs.frends.com/tasks/tasks/<system>/<method>.md`, e.g. `/tasks/tasks/http/request.md`, `/tasks/tasks/sftp/uploadfiles.md`, `/tasks/tasks/microsoft-sql-server/executequery.md`. One index page per system (`/tasks/tasks/http.md`) listing its methods. All pages support `.md` and the `?ask=` query. The full list of systems and methods is in `https://docs.frends.com/llms.txt` under "## Tasks".
2. **`https://tasks.frends.com`** — the searchable portal (categories: AWS, Azure, Databases, ERP, CRM, File Formats, Messaging, Protocols, SaaS, …). Still online; each task page shows parameters, versions and links. Treat docs.frends.com/tasks as the canonical source going forward — the standalone portal has been discussed for deprecation.
3. **Source code:** `https://github.com/FrendsPlatform/Frends.<Package>` — one repo per new-generation package (Frends.HTTP, Frends.SFTP, Frends.AzureBlobStorage, Frends.MicrosoftSQL, …). The source is the ground truth for parameter classes (`Frends.X.Y.Definitions.*`) and behavior. Older multi-task repos (e.g. `Frends.Web`, `Frends.File`) and `CommunityHiQ/*` community repos are legacy — check README warnings.

## Coverage highlights (from the current catalog)

Cloud storage/queues (Amazon S3/SQS/Kinesis, Azure Blob/Data Lake/Event Hub/Service Bus, Google Cloud Storage/BigQuery/Pub-Sub/Drive/Sheets), databases (SQL Server incl. BulkInsert/BatchOperation/ExecuteProcedure, Oracle, PostgreSQL, MySQL, Snowflake, MongoDB, Cassandra, IBM Db2, ODBC, Redis), files & transfer (Files, SFTP, FTP, SMB, PGP, HTTP DownloadFile), formats (CSV, Excel, ODF, JSON incl. Query/Transform/Validate/Handlebars, XML incl. XSLT/XPath/Validate, Avro, Fixed-width, PDF), EDI & healthcare (Edifact, X12, AS2, HL7v2, MLLP), enterprise apps (SAP S4/HANA OData, SAP SuccessFactors, Dynamics 365, Salesforce incl. Pub/Sub, ServiceNow, Jira, Confluence, HubSpot, Shopify, Odoo, Oracle Fusion, IBM Maximo), messaging (Kafka, RabbitMQ, IBM MQ, MQTT, AMQP, Teams, Slack, SMTP/Exchange/IMAP), scripting (PowerShell, Python, Utilities.RunProcess), auth (OAuth CreateJWTToken/ParseToken), AI (OpenAI.CallChatGPT), and **PlatformApi.Request** for driving Frends itself.

## Version guidance

You do **not** always need the latest Task version. Existing Processes pin the version that's imported in the Tenant; upgrading a Task package can change parameter classes and behavior — treat Task upgrades as changes to review and test, especially where Code Tasks construct `Frends.X.Y.Definitions` objects (those type names follow the package version). When reviewing an export, `LinkedTasks` / `UsedTasksJson` show exactly which package versions a Process depends on.
