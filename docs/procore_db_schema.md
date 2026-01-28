generator client {
  provider      = "prisma-client-js"
  binaryTargets = ["native", "rhel-openssl-3.0.x"]
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model api_credentials {
  id              Int      @id @default(autoincrement())
  credential_type String   @default("procore_oauth")
  access_token    String
  refresh_token   String?
  token_type      String   @default("Bearer")
  expires_at      DateTime
  company_id      Int?
  scope           String?
  created_at      DateTime @default(now())
  updated_at      DateTime

  @@index([credential_type])
  @@index([expires_at])
}

model audit_records {
  id                  String   @id
  application_id      String
  timestamp           DateTime @default(now())
  procore_entity_type String
  operation           String
  request_parameters  Json
  response_status     String
  response_data       Json?
  errors              Json?
  expires_at          DateTime

  @@index([application_id])
  @@index([expires_at])
  @@index([procore_entity_type])
  @@index([timestamp])
}

model budget_line_items {
  id                            BigInt       @id
  project_id                    BigInt
  budget_view_id                BigInt
  biller_type                   String?
  biller_id                     BigInt?
  cost_code_id                  BigInt?
  cost_code_name                String?
  root_cost_code_id             BigInt?
  root_cost_code_name           String?
  category_id                   BigInt?
  description                   String?
  original_budget_amount        Decimal?     @db.Decimal(15, 2)
  approved_budget_changes       Decimal?     @db.Decimal(15, 2)
  approved_change_orders        Decimal?     @db.Decimal(15, 2)
  revised_budget                Decimal?     @db.Decimal(15, 2)
  pending_change_orders         Decimal?     @db.Decimal(15, 2)
  projected_budget              Decimal?     @db.Decimal(15, 2)
  committed_costs               Decimal?     @db.Decimal(15, 2)
  direct_costs                  Decimal?     @db.Decimal(15, 2)
  job_to_date_costs             Decimal?     @db.Decimal(15, 2)
  pending_cost_changes          Decimal?     @db.Decimal(15, 2)
  projected_costs               Decimal?     @db.Decimal(15, 2)
  forecast_to_complete          Decimal?     @db.Decimal(15, 2)
  is_forecast_manual            Boolean      @default(false)
  manual_forecast_amount        Decimal?     @db.Decimal(15, 2)
  automatic_forecast_amount     Decimal?     @db.Decimal(15, 2)
  forecast_calculation_strategy String?
  forecast_notes                String?
  budget_forecast_id            BigInt?
  estimated_cost_at_completion  Decimal?     @db.Decimal(15, 2)
  budgeted                      Boolean      @default(true)
  origin_id                     BigInt?
  origin_data                   String?
  additional_columns            Json?
  created_at                    DateTime
  updated_at                    DateTime
  last_synced_at                DateTime     @default(now())
  budget_views                  budget_views @relation(fields: [budget_view_id], references: [id], onDelete: Cascade)
  projects                      projects     @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([budget_view_id])
  @@index([budgeted])
  @@index([category_id])
  @@index([cost_code_id])
  @@index([is_forecast_manual])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([root_cost_code_id])
}

model budget_views {
  id                BigInt              @id
  project_id        BigInt
  name              String
  view_type         String
  is_default        Boolean             @default(false)
  created_at        DateTime
  updated_at        DateTime
  last_synced_at    DateTime            @default(now())
  budget_line_items budget_line_items[]
  projects          projects            @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([project_id])
  @@index([view_type])
}

model change_orders {
  id                   BigInt   @id
  project_id           BigInt
  number               String?
  title                String
  description          String?
  status               String
  cost_impact          Decimal? @db.Decimal(15, 2)
  schedule_impact      Int?
  package_type         String?
  created_at           DateTime
  updated_at           DateTime
  last_synced_at       DateTime @default(now())
  custom_fields        Json?
  attachment_s3_keys   Json?
  projects             projects @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([updated_at])
}

model change_events {
  id                        BigInt   @id
  project_id                BigInt
  number                    Int?
  alphanumeric_number       String?
  title                     String
  description               String?
  status                    String
  event_type                String?
  event_scope               String?
  change_reason             String?
  change_event_status_id    BigInt?
  change_event_status_name  String?
  created_by_id             BigInt?
  created_by_name           String?
  created_at                DateTime
  updated_at                DateTime
  last_synced_at            DateTime @default(now())
  change_event_line_items   Json?
  rfqs                      Json?
  custom_fields             Json?
  attachment_s3_keys        Json?
  projects                  projects @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([event_type])
  @@index([updated_at])
}

model commitment_contract_items {
  id                     BigInt               @id
  commitment_contract_id BigInt
  project_id             BigInt
  vendor_id              BigInt
  wbs_code_id            BigInt?
  prime_line_item_id     BigInt?
  amount                 Decimal              @db.Decimal(15, 2)
  description            String?
  quantity               Decimal?             @db.Decimal(15, 4)
  unit_cost              Decimal?             @db.Decimal(15, 4)
  uom                    String?
  tax_code_id            BigInt?
  created_at             DateTime
  updated_at             DateTime
  last_synced_at         DateTime             @default(now())
  commitment_contracts   commitment_contracts @relation(fields: [commitment_contract_id], references: [id], onDelete: Cascade)
  projects               projects             @relation(fields: [project_id], references: [id], onDelete: Cascade)
  vendors                vendors              @relation(fields: [vendor_id], references: [id])

  @@index([commitment_contract_id])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([vendor_id])
  @@index([wbs_code_id])
}

model commitment_contracts {
  id                                 BigInt                      @id
  project_id                         BigInt
  vendor_id                          BigInt
  type                               String
  number                             String
  title                              String
  description                        String?
  status                             String
  executed                           Boolean                     @default(false)
  signature_required                 Boolean                     @default(false)
  private                            Boolean                     @default(true)
  show_line_items_to_non_admins      Boolean                     @default(false)
  accessor_ids                       Json?
  billing_schedule_of_values_status  String?
  enable_ssov                        Boolean                     @default(false)
  show_cost_code_on_pdf              Boolean                     @default(false)
  inclusions                         String?
  exclusions                         String?
  retainage_percent                  Decimal?                    @db.Decimal(5, 2)
  accounting_method                  String?
  payment_terms                      String?
  currency_exchange_rate             Decimal?                    @db.Decimal(10, 4)
  currency_iso_code                  String?
  allow_payment_applications         Boolean                     @default(true)
  allow_payments                     Boolean                     @default(true)
  allow_comments                     Boolean                     @default(true)
  allow_markups                      Boolean                     @default(true)
  display_materials_retainage        Boolean                     @default(false)
  display_work_retainage             Boolean                     @default(false)
  change_order_level_of_detail       String?
  ssr_enabled                        Boolean                     @default(false)
  bill_to_address                    String?
  ship_to_address                    String?
  ship_via                           String?
  actual_completion_date             DateTime?                   @db.Date
  approval_letter_date               DateTime?                   @db.Date
  contract_date                      DateTime?                   @db.Date
  contract_estimated_completion_date DateTime?                   @db.Date
  contract_start_date                DateTime?                   @db.Date
  delivery_date                      DateTime?                   @db.Date
  execution_date                     DateTime?                   @db.Date
  issued_on_date                     DateTime?                   @db.Date
  letter_of_intent_date              DateTime?                   @db.Date
  returned_date                      DateTime?                   @db.Date
  signed_contract_received_date      DateTime?                   @db.Date
  assignee_id                        BigInt?
  bill_recipient_ids                 Json?
  attachments_s3_keys                Json?
  attachment_ids                     Json?
  drawing_revision_ids               Json?
  file_version_ids                   Json?
  form_ids                           Json?
  image_ids                          Json?
  origin_id                          String?
  origin_code                        String?
  origin_data                        String?
  custom_fields                      Json?
  created_at                         DateTime
  updated_at                         DateTime
  last_synced_at                     DateTime                    @default(now())
  commitment_contract_items          commitment_contract_items[]
  commitment_change_orders           commitment_change_orders[]
  projects                           projects                    @relation(fields: [project_id], references: [id], onDelete: Cascade)
  vendors                            vendors                     @relation(fields: [vendor_id], references: [id])
  invoice_submissions                invoice_submissions[]
  requisitions                       requisitions[]

  @@index([actual_completion_date])
  @@index([contract_date])
  @@index([contract_estimated_completion_date])
  @@index([contract_start_date])
  @@index([executed])
  @@index([issued_on_date])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([type])
  @@index([vendor_id])
}

model commitment_change_orders {
  id                                BigInt                           @id
  project_id                        BigInt
  contract_id                       BigInt
  number                            String
  title                             String
  description                       String?
  status                            String
  grand_total                       Decimal                          @db.Decimal(15, 2)
  executed                          Boolean                          @default(false)
  paid                              Boolean                          @default(false)
  private                           Boolean                          @default(true)
  signature_required                Boolean                          @default(false)
  field_change                      Boolean                          @default(false)
  revision                          Int?
  reference                         String?
  type                              String?
  batch_id                          BigInt?
  legacy_package_id                 BigInt?
  legacy_request_id                 BigInt?
  location_id                       BigInt?
  schedule_impact_amount            Decimal?                         @db.Decimal(15, 2)
  change_order_change_reason        String?
  due_date                          DateTime?                        @db.Date
  invoiced_date                     DateTime?                        @db.Date
  paid_date                         DateTime?                        @db.Date
  signed_change_order_received_date DateTime?                        @db.Date
  reviewed_at                       DateTime?
  created_by_id                     BigInt?
  created_by_name                   String?
  designated_reviewer_id            BigInt?
  received_from_id                  BigInt?
  reviewed_by_id                    BigInt?
  currency_configuration            Json?
  custom_fields                     Json?
  attachments                       Json?
  attachments_s3_keys               Json?
  created_at                        DateTime
  updated_at                        DateTime
  last_synced_at                    DateTime                         @default(now())
  commitment_change_order_items     commitment_change_order_items[]
  commitment_contracts              commitment_contracts             @relation(fields: [contract_id], references: [id], onDelete: Cascade)
  projects                          projects                         @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([batch_id])
  @@index([contract_id])
  @@index([executed])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([updated_at])
}

model commitment_change_order_items {
  id                        BigInt                   @id
  commitment_change_order_id BigInt
  project_id                BigInt
  prime_line_item_id        BigInt?
  commitment_line_item_id   BigInt?
  wbs_code_id               BigInt?
  tax_code_id               BigInt?
  description               String?
  uom                       String?
  quantity                  Decimal?                 @db.Decimal(15, 4)
  unit_cost                 Decimal?                 @db.Decimal(15, 4)
  amount                    Decimal                  @db.Decimal(15, 2)
  extended_type             String?
  position                  Int?
  wbs_code                  Json?
  created_at                DateTime                 @default(now())
  updated_at                DateTime                 @default(now())
  last_synced_at            DateTime                 @default(now())
  commitment_change_orders  commitment_change_orders @relation(fields: [commitment_change_order_id], references: [id], onDelete: Cascade)
  projects                  projects                 @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([commitment_change_order_id])
  @@index([commitment_line_item_id])
  @@index([last_synced_at])
  @@index([prime_line_item_id])
  @@index([project_id])
  @@index([wbs_code_id])
}

model company_users {
  id                     BigInt          @id
  company_id             BigInt
  login                  String
  name                   String
  first_name             String?
  last_name              String?
  job_title              String?
  email_address          String
  business_phone         String?
  mobile_phone           String?
  employee_id            String?
  is_employee            Boolean         @default(false)
  vendor_id              BigInt?
  trade_name             String?
  notes                  String?
  avatar_url             String?
  permission_template_id BigInt?
  is_active              Boolean         @default(true)
  created_at             DateTime
  updated_at             DateTime
  last_synced_at         DateTime        @default(now())
  vendors                vendors?        @relation(fields: [vendor_id], references: [id])
  project_users          project_users[]

  @@index([company_id])
  @@index([company_id, is_active])
  @@index([email_address])
  @@index([is_active])
  @@index([last_synced_at])
  @@index([vendor_id])
}

model daily_logs {
  id                  BigInt   @id
  project_id          BigInt
  log_type            String
  log_date            DateTime @db.Date
  description         String?
  location_id         Int?
  multi_tier_location Json?
  created_at          DateTime
  updated_at          DateTime
  log_data            Json
  last_synced_at      DateTime @default(now())
  projects            projects @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([log_date])
  @@index([project_id, log_date])
  @@index([project_id, log_type])
}

model documents {
  id              BigInt      @id
  project_id      BigInt
  folder_id       Int?
  name            String
  url             String?
  size            Int?
  file_type       String?
  is_folder       Boolean     @default(false)
  parent_id       BigInt?
  created_at      DateTime
  updated_at      DateTime
  last_synced_at  DateTime    @default(now())
  documents       documents?  @relation("documentsTodocuments", fields: [parent_id], references: [id])
  other_documents documents[] @relation("documentsTodocuments")
  projects        projects    @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([folder_id])
  @@index([is_folder])
  @@index([last_synced_at])
  @@index([parent_id])
  @@index([project_id])
}

model drawing_areas {
  id                BigInt              @id
  project_id        BigInt
  name              String
  created_at        DateTime
  updated_at        DateTime
  last_synced_at    DateTime            @default(now())
  projects          projects            @relation(fields: [project_id], references: [id], onDelete: Cascade)
  drawing_revisions drawing_revisions[]
  drawings          drawings[]

  @@index([last_synced_at])
  @@index([project_id])
}

model drawing_revisions {
  id              BigInt        @id
  project_id      BigInt
  drawing_id      BigInt
  drawing_area_id BigInt
  drawing_set_id  BigInt?
  revision_number String?
  current         Boolean       @default(false)
  s3_key          String?
  filename        String?
  file_size       Int?
  created_at      DateTime
  updated_at      DateTime
  last_synced_at  DateTime      @default(now())
  drawing_areas   drawing_areas @relation(fields: [drawing_area_id], references: [id], onDelete: Cascade)
  drawings        drawings      @relation(fields: [drawing_id], references: [id], onDelete: Cascade)
  drawing_sets    drawing_sets? @relation(fields: [drawing_set_id], references: [id])
  projects        projects      @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([current])
  @@index([drawing_area_id])
  @@index([drawing_id])
  @@index([drawing_set_id])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([s3_key])
}

model drawing_sets {
  id                BigInt              @id
  project_id        BigInt
  name              String
  set_date          DateTime?           @db.Date
  created_at        DateTime
  updated_at        DateTime
  last_synced_at    DateTime            @default(now())
  drawing_revisions drawing_revisions[]
  projects          projects            @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([project_id])
  @@index([set_date])
}

model drawings {
  id                BigInt              @id
  project_id        BigInt
  drawing_area_id   BigInt
  drawing_number    String
  title             String?
  discipline        String?
  created_at        DateTime
  updated_at        DateTime
  last_synced_at    DateTime            @default(now())
  drawing_revisions drawing_revisions[]
  drawing_areas     drawing_areas       @relation(fields: [drawing_area_id], references: [id], onDelete: Cascade)
  projects          projects            @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@unique([project_id, drawing_number])
  @@index([discipline])
  @@index([drawing_area_id])
  @@index([last_synced_at])
  @@index([project_id])
}

model integration_request_events {
  id                          String                       @id
  event_type                  String
  application_id              String
  timestamp                   DateTime                     @default(now())
  procore_entity_type         String
  operation                   String
  request_parameters          Json
  integration_response_events integration_response_events?

  @@index([application_id])
  @@index([event_type])
  @@index([procore_entity_type])
  @@index([timestamp])
}

model integration_response_events {
  id                         String                     @id
  request_id                 String                     @unique
  timestamp                  DateTime                   @default(now())
  success                    Boolean
  data_payload               Json?
  error_details              Json?
  integration_request_events integration_request_events @relation(fields: [request_id], references: [id], onDelete: Cascade)

  @@index([request_id])
  @@index([success])
  @@index([timestamp])
}

model invoice_submissions {
  id                     String               @id
  external_invoice_id    String               @unique
  project_id             BigInt
  commitment_id          BigInt
  invoice_number         String
  status                 String
  billing_amount         Decimal?             @db.Decimal(15, 2)
  procore_requisition_id BigInt?
  request_payload        Json
  response_payload       Json?
  error_message          String?
  retry_count            Int                  @default(0)
  submitted_at           DateTime             @default(now())
  completed_at           DateTime?
  commitment_contracts   commitment_contracts @relation(fields: [commitment_id], references: [id], onDelete: Cascade)
  projects               projects             @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@unique([project_id, commitment_id, invoice_number])
  @@index([commitment_id])
  @@index([procore_requisition_id])
  @@index([project_id])
  @@index([status])
  @@index([submitted_at])
}

model photos {
  id                BigInt    @id
  project_id        BigInt
  url               String
  thumbnail_url     String?
  s3_key            String?
  image_category_id BigInt
  description       String?
  location          String?
  taken_at          DateTime?
  created_at        DateTime
  updated_at        DateTime
  last_synced_at    DateTime  @default(now())
  projects          projects  @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([created_at])
  @@index([image_category_id])
  @@index([last_synced_at])
  @@index([project_id])
}

model prime_contract_change_orders {
  id                                BigInt          @id
  prime_contract_id                 BigInt
  batch_id                          BigInt?
  number                            String
  title                             String
  description                       String?
  status                            String
  executed                          Boolean         @default(false)
  grand_total                       Decimal         @db.Decimal(15, 2)
  schedule_impact_amount            Decimal?        @db.Decimal(15, 2)
  change_reason_id                  BigInt?
  change_reason_text                String?
  type                              String?
  revision                          Int?
  reference                         String?
  field_change                      Boolean         @default(false)
  paid                              Boolean         @default(false)
  private                           Boolean         @default(false)
  signature_required                Boolean         @default(false)
  created_by_id                     BigInt?
  created_by_name                   String?
  reviewed_by_id                    BigInt?
  designated_reviewer_id            BigInt?
  received_from_id                  BigInt?
  location_id                       BigInt?
  created_at                        DateTime
  updated_at                        DateTime
  reviewed_at                       DateTime?
  due_date                          DateTime?       @db.Date
  invoiced_date                     DateTime?       @db.Date
  paid_date                         DateTime?       @db.Date
  signed_change_order_received_date DateTime?       @db.Date
  last_synced_at                    DateTime        @default(now())
  legacy_package_id                 BigInt?
  legacy_request_id                 BigInt?
  origin_id                         String?
  origin_code                       String?
  custom_fields                     Json?
  currency_configuration            Json?
  prime_contracts                   prime_contracts @relation(fields: [prime_contract_id], references: [id], onDelete: Cascade)

  @@index([batch_id])
  @@index([executed])
  @@index([last_synced_at])
  @@index([prime_contract_id])
  @@index([status])
  @@index([updated_at])
}

model prime_contract_line_items {
  id                 BigInt          @id
  prime_contract_id  BigInt
  position           Int?
  description        String?
  cost_code_id       BigInt?
  line_item_type_id  BigInt?
  line_item_group_id BigInt?
  tax_code_id        BigInt?
  amount             Decimal         @db.Decimal(15, 2)
  quantity           Decimal?        @db.Decimal(15, 4)
  unit_cost          Decimal?        @db.Decimal(15, 2)
  tax_amount         Decimal?        @db.Decimal(15, 2)
  wbs_code_id        BigInt?
  extended_type      String?
  extended_data      Json?
  created_at         DateTime
  updated_at         DateTime
  last_synced_at     DateTime        @default(now())
  origin_id          String?
  origin_code        String?
  origin_data        String?
  prime_contracts    prime_contracts @relation(fields: [prime_contract_id], references: [id], onDelete: Cascade)

  @@index([cost_code_id])
  @@index([last_synced_at])
  @@index([prime_contract_id])
  @@index([wbs_code_id])
}

model prime_contracts {
  id                                   BigInt                         @id
  project_id                           BigInt
  number                               String?
  title                                String
  description                          String?
  status                               String
  executed                             Boolean                        @default(false)
  private                              Boolean                        @default(false)
  grand_total                          Decimal                        @db.Decimal(15, 2)
  revised_contract_amount              Decimal                        @db.Decimal(15, 2)
  approved_change_orders               Decimal                        @db.Decimal(15, 2)
  pending_change_orders_amount         Decimal                        @db.Decimal(15, 2)
  draft_change_orders_amount           Decimal                        @db.Decimal(15, 2)
  pending_revised_contract_amount      Decimal                        @db.Decimal(15, 2)
  owner_invoices_amount                Decimal                        @db.Decimal(15, 2)
  total_payments                       Decimal                        @db.Decimal(15, 2)
  outstanding_balance                  Decimal                        @db.Decimal(15, 2)
  percentage_paid                      Decimal                        @db.Decimal(15, 10)
  retainage_percent                    Decimal?                       @db.Decimal(5, 2)
  contract_date                        DateTime?                      @db.Date
  issued_on_date                       DateTime?                      @db.Date
  execution_date                       DateTime?                      @db.Date
  signed_contract_received_date        DateTime?                      @db.Date
  letter_of_intent_date                DateTime?                      @db.Date
  approval_letter_date                 DateTime?                      @db.Date
  returned_date                        DateTime?                      @db.Date
  contract_start_date                  DateTime?                      @db.Date
  contract_estimated_completion_date   DateTime?                      @db.Date
  original_substantial_completion_date DateTime?                      @db.Date
  substantial_completion_date          DateTime?                      @db.Date
  actual_completion_date               DateTime?                      @db.Date
  contract_termination_date            DateTime?                      @db.Date
  accounting_method                    String?
  contractor_id                        BigInt?
  vendor_id                            BigInt?
  architect_id                         BigInt?
  inclusions                           String?
  exclusions                           String?
  show_line_items_to_non_admins        Boolean                        @default(false)
  has_change_order_packages            Boolean                        @default(false)
  has_potential_change_orders          Boolean                        @default(false)
  attachments                          Json?
  created_at                           DateTime
  updated_at                           DateTime
  deleted_at                           DateTime?
  last_synced_at                       DateTime                       @default(now())
  created_by_id                        BigInt?
  custom_fields                        Json?
  origin_id                            String?
  origin_code                          String?
  origin_data                          String?
  currency_iso_code                    String?
  owner_invoices                       owner_invoices[]
  prime_contract_change_orders         prime_contract_change_orders[]
  prime_contract_line_items            prime_contract_line_items[]
  projects                             projects                       @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([contractor_id])
  @@index([executed])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([updated_at])
  @@index([vendor_id])
}

model owner_invoices {
  id                                     BigInt          @id
  prime_contract_id                      BigInt
  project_id                             BigInt
  number                                 Int
  invoice_number                         String?
  status                                 String
  billing_date                           DateTime?       @db.Date
  period_start                           DateTime?       @db.Date
  period_end                             DateTime?       @db.Date
  period_id                              BigInt?
  percent_complete                       Decimal?        @db.Decimal(10, 2)
  total_amount_paid                      Decimal         @db.Decimal(15, 2)
  total_amount_accrued_this_period       Decimal?        @db.Decimal(15, 2)
  // G702 fields (AIA Document G702)
  current_payment_due                    Decimal         @db.Decimal(15, 2)
  total_earned_less_retainage            Decimal?        @db.Decimal(15, 2)
  balance_to_finish_including_retainage  Decimal?        @db.Decimal(15, 2)
  original_contract_sum                  Decimal?        @db.Decimal(15, 2)
  contract_sum_to_date                   Decimal?        @db.Decimal(15, 2)
  net_change_by_change_orders            Decimal?        @db.Decimal(15, 2)
  total_completed_and_stored_to_date     Decimal?        @db.Decimal(15, 2)
  total_retainage                        Decimal?        @db.Decimal(15, 2)
  less_previous_certificates_for_payment Decimal?        @db.Decimal(15, 2)
  // Metadata
  origin_id                              String?
  origin_data                            String?
  formatted_contract_company             String?
  currency_configuration                 Json?
  created_at                             DateTime
  updated_at                             DateTime
  last_synced_at                         DateTime        @default(now())
  prime_contracts                        prime_contracts @relation(fields: [prime_contract_id], references: [id], onDelete: Cascade)
  projects                               projects        @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([prime_contract_id])
  @@index([project_id])
  @@index([status])
  @@index([billing_date])
  @@index([last_synced_at])
}

model processed_webhook_events {
  id            String   @id
  ulid          String   @unique
  event_id      BigInt   @unique
  resource_name String
  event_type    String
  resource_id   BigInt
  processed_at  DateTime @default(now())
  expires_at    DateTime

  @@index([expires_at])
  @@index([processed_at])
  @@index([resource_name, event_type])
  @@index([ulid])
}

model project_users {
  id                       String        @id
  user_id                  BigInt
  project_id               BigInt
  company_id               BigInt
  permission_template_id   BigInt?
  permission_template_name String?
  is_employee              Boolean       @default(false)
  vendor_id                BigInt?
  employee_id              String?
  role_ids                 Json?
  cost_code_id             BigInt?
  created_at               DateTime
  updated_at               DateTime
  last_synced_at           DateTime      @default(now())
  projects                 projects      @relation(fields: [project_id], references: [id], onDelete: Cascade)
  company_users            company_users @relation(fields: [user_id], references: [id], onDelete: Cascade)
  vendors                  vendors?      @relation(fields: [vendor_id], references: [id])

  @@unique([project_id, user_id])
  @@index([company_id])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([user_id])
  @@index([vendor_id])
}

model project_roles {
  id             BigInt   @id
  project_id     BigInt
  user_id        BigInt
  contact_id     BigInt
  role_name      String
  user_name      String
  is_active      Boolean  @default(true)
  created_at     DateTime
  last_synced_at DateTime @default(now())
  projects       projects @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@unique([project_id, user_id, role_name])
  @@index([is_active])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([role_name])
  @@index([user_id])
}

model projects {
  id                              BigInt                            @id
  name                            String
  display_name                    String?
  project_number                  String?
  address                         String?
  city                            String?
  state_code                      String?
  country_code                    String?
  zip                             String?
  active                          Boolean                           @default(true)
  estimated_start_date            DateTime?                         @db.Date
  estimated_completion_date       DateTime?                         @db.Date
  created_at                      DateTime
  updated_at                      DateTime
  last_synced_at                  DateTime                          @default(now())
  budget_line_items               budget_line_items[]
  budget_views                    budget_views[]
  change_events                   change_events[]
  change_orders                   change_orders[]
  commitment_contract_items       commitment_contract_items[]
  commitment_contracts            commitment_contracts[]
  commitment_change_orders        commitment_change_orders[]
  commitment_change_order_items   commitment_change_order_items[]
  daily_logs                      daily_logs[]
  documents                       documents[]
  drawing_areas                   drawing_areas[]
  drawing_revisions               drawing_revisions[]
  drawing_sets                    drawing_sets[]
  drawings                        drawings[]
  invoice_submissions             invoice_submissions[]
  owner_invoices                  owner_invoices[]
  photos                          photos[]
  prime_contracts                 prime_contracts[]
  project_roles                   project_roles[]
  project_users                   project_users[]
  requisitions                    requisitions[]
  rfis                            rfis[]
  specification_section_divisions specification_section_divisions[]
  specification_section_revisions specification_section_revisions[]
  specification_sections          specification_sections[]
  submittal_attachments           submittal_attachments[]
  submittals                      submittals[]
  timesheets                      timesheets[]
  direct_costs                    direct_costs[]

  @@index([active])
  @@index([last_synced_at])
  @@index([updated_at])
}

model requisitions {
  id                     BigInt                @id
  project_id             BigInt
  commitment_id          BigInt?
  commitment_type        String
  invoice_number         String
  number                 Int
  billing_date           DateTime?             @db.Date
  payment_date           DateTime?             @db.Date
  requisition_start      DateTime?             @db.Date
  requisition_end        DateTime?             @db.Date
  status                 String
  percent_complete       String?
  submitted_at           DateTime?
  comment                String?
  final                  Boolean               @default(false)
  vendor_name            String?
  created_by             Json?
  summary                Json
  attachments            Json?
  attachments_s3_keys    Json?
  origin_id              String?
  origin_data            String?
  period_id              BigInt?
  custom_fields          Json?
  currency_configuration Json?
  created_at             DateTime
  updated_at             DateTime
  last_synced_at         DateTime              @default(now())
  commitment_contracts   commitment_contracts? @relation(fields: [commitment_id], references: [id], onDelete: Cascade)
  projects               projects              @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([billing_date])
  @@index([commitment_id])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([updated_at])
}

model rfis {
  id                                   BigInt    @id
  project_id                           BigInt
  number                               String
  subject                              String
  question                             String?
  status                               String
  assignee_id                          BigInt?
  responsible_contractor_id            BigInt?
  due_date                             DateTime? @db.Date
  created_at                           DateTime
  updated_at                           DateTime
  last_synced_at                       DateTime  @default(now())
  custom_fields                        Json?
  official_response_attachment_s3_keys Json?
  official_responses                   Json?
  projects                             projects  @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@unique([project_id, number])
  @@index([assignee_id])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([updated_at])
}

model specification_section_divisions {
  id                     BigInt                   @id
  project_id             BigInt
  number                 String
  description            String
  url                    String?
  created_at             DateTime                 @default(now())
  updated_at             DateTime                 @default(now())
  last_synced_at         DateTime                 @default(now())
  projects               projects                 @relation(fields: [project_id], references: [id], onDelete: Cascade)
  specification_sections specification_sections[]

  @@unique([project_id, number])
  @@index([last_synced_at])
  @@index([number])
  @@index([project_id])
}

model specification_section_revisions {
  id                                BigInt                 @id
  project_id                        BigInt
  specification_section_id          BigInt
  specification_section_division_id BigInt
  specification_set_id              BigInt?
  number                            String
  description                       String
  revision                          String?
  issued_date                       DateTime?
  received_date                     DateTime?
  s3_key                            String?
  filename                          String?
  file_size                         Int?
  created_at                        DateTime               @default(now())
  updated_at                        DateTime
  last_synced_at                    DateTime               @default(now())
  custom_fields                     Json?
  projects                          projects               @relation(fields: [project_id], references: [id], onDelete: Cascade)
  specification_sections            specification_sections @relation(fields: [specification_section_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([number])
  @@index([project_id])
  @@index([s3_key])
  @@index([specification_section_division_id])
  @@index([specification_section_id])
  @@index([specification_set_id])
}

model specification_sections {
  id                                BigInt                            @id
  project_id                        BigInt
  specification_section_division_id BigInt?
  number                            String
  label                             String
  description                       String
  current_revision_id               BigInt?
  created_at                        DateTime                          @default(now())
  updated_at                        DateTime                          @default(now())
  last_synced_at                    DateTime                          @default(now())
  specification_section_revisions   specification_section_revisions[]
  projects                          projects                          @relation(fields: [project_id], references: [id], onDelete: Cascade)
  specification_section_divisions   specification_section_divisions?  @relation(fields: [specification_section_division_id], references: [id])

  @@unique([project_id, number])
  @@index([current_revision_id])
  @@index([last_synced_at])
  @@index([number])
  @@index([project_id])
  @@index([specification_section_division_id])
}

model submittal_attachments {
  id             BigInt     @id
  submittal_id   BigInt
  project_id     BigInt
  approver_id    BigInt?
  filename       String
  s3_key         String?
  file_size      Int?
  content_type   String?
  created_at     DateTime
  updated_at     DateTime
  last_synced_at DateTime   @default(now())
  projects       projects   @relation(fields: [project_id], references: [id], onDelete: Cascade)
  submittals     submittals @relation(fields: [submittal_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([project_id])
  @@index([submittal_id])
}

model submittals {
  id                                   BigInt                  @id
  project_id                           BigInt
  number                               String
  title                                String
  description                          String?
  status_id                            BigInt
  received_from_id                     BigInt?
  spec_section                         String?
  due_date                             DateTime?               @db.Date
  revision_number                      Int?                    @default(1)
  created_at                           DateTime
  updated_at                           DateTime
  last_synced_at                       DateTime                @default(now())
  custom_fields                        Json?
  official_response_attachment_s3_keys Json?
  official_responses                   Json?
  submittal_attachments                submittal_attachments[]
  projects                             projects                @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([last_synced_at])
  @@index([project_id])
  @@index([project_id, number])
  @@index([status_id])
  @@index([updated_at])
}

model sync_events {
  id              String    @id
  sync_type       String
  status          String
  start_time      DateTime  @default(now())
  completion_time DateTime?
  entity_types    Json
  record_counts   Json
  errors          Json?

  @@index([start_time])
  @@index([status])
  @@index([sync_type])
}

model timesheets {
  id               BigInt   @id
  project_id       BigInt
  date             DateTime @db.Date
  name             String
  number           Int
  status           String
  created_by       Json
  timecard_entries Json
  created_at       DateTime
  updated_at       DateTime
  last_synced_at   DateTime @default(now())
  projects         projects @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@index([date])
  @@index([last_synced_at])
  @@index([project_id])
  @@index([status])
  @@index([updated_at])
}

model vendor_insurances {
  id                                     BigInt    @id
  vendor_id                              BigInt
  name                                   String
  insurance_type                         String
  policy_number                          String?
  limit                                  String?
  effective_date                         DateTime? @db.Date
  expiration_date                        DateTime? @db.Date
  status                                 String
  exempt                                 Boolean   @default(false)
  info_received                          Boolean   @default(false)
  enable_expired_insurance_notifications Boolean   @default(false)
  notes                                  String?
  additional_insured                     String?
  division_template                      String?
  insurance_sets                         String?
  origin_id                              String?
  origin_data                            String?
  created_at                             DateTime
  updated_at                             DateTime
  last_synced_at                         DateTime  @default(now())
  vendors                                vendors   @relation(fields: [vendor_id], references: [id], onDelete: Cascade)

  @@index([expiration_date])
  @@index([insurance_type])
  @@index([last_synced_at])
  @@index([status])
  @@index([vendor_id])
}

model vendors {
  id                        BigInt                      @id
  company_id                BigInt
  name                      String
  abbreviated_name          String?
  address                   String?
  city                      String?
  state_code                String?
  zip                       String?
  country_code              String?
  business_phone            String?
  mobile_phone              String?
  fax_number                String?
  email_address             String?
  website                   String?
  trade_name                String?
  license_number            String?
  labor_union               String?
  authorized_bidder         Boolean                     @default(false)
  prequalified              Boolean                     @default(false)
  is_active                 Boolean                     @default(true)
  union_member              Boolean                     @default(false)
  non_union_prevailing_wage Boolean                     @default(false)
  notes                     String?
  parent_id                 BigInt?
  primary_contact_id        BigInt?
  origin_id                 String?
  origin_code               String?
  origin_data               String?
  bidding_qualifications    Json?
  created_at                DateTime
  updated_at                DateTime
  last_synced_at            DateTime                    @default(now())
  commitment_contract_items commitment_contract_items[]
  commitment_contracts      commitment_contracts[]
  company_users             company_users[]
  project_users             project_users[]
  vendor_insurances         vendor_insurances[]
  vendors                   vendors?                    @relation("vendorsTovendors", fields: [parent_id], references: [id])
  other_vendors             vendors[]                   @relation("vendorsTovendors")
  direct_costs              direct_costs[]

  @@index([authorized_bidder])
  @@index([company_id])
  @@index([is_active])
  @@index([last_synced_at])
  @@index([parent_id])
  @@index([prequalified])
}

model webhook_health_metrics {
  id                    String   @id
  hook_id               String
  company_id            BigInt
  timestamp             DateTime @default(now())
  total_deliveries      Int
  successful_deliveries Int
  failing_deliveries    Int
  discarded_deliveries  Int
  success_rate          Float
  failure_rate          Float
  by_resource_type      Json

  @@index([company_id])
  @@index([hook_id])
  @@index([timestamp])
}

model webhook_hooks {
  id               String             @id
  procore_hook_id  String             @unique
  company_id       BigInt
  namespace        String
  api_version      String             @default("v2")
  destination_url  String
  environment      String             @default("production")
  active           Boolean            @default(true)
  created_at       DateTime           @default(now())
  updated_at       DateTime
  webhook_triggers webhook_triggers[]

  @@index([active])
  @@index([company_id])
  @@index([environment])
}

model webhook_triggers {
  id                 String        @id
  hook_id            String
  resource_name      String
  event_type         String
  procore_trigger_id String?
  created_at         DateTime      @default(now())
  webhook_hooks      webhook_hooks @relation(fields: [hook_id], references: [id], onDelete: Cascade)

  @@unique([hook_id, resource_name, event_type])
  @@index([hook_id])
  @@index([resource_name])
}

model direct_costs {
  id                     BigInt              @id
  project_id             BigInt
  vendor_id              BigInt?
  direct_cost_type       String
  direct_cost_date       DateTime            @db.Date
  status                 String?
  invoice_number         String?
  description            String?             @db.Text
  payment_date           DateTime?           @db.Date
  received_date          DateTime?           @db.Date
  terms                  String?
  grand_total            Decimal             @db.Decimal(15, 2)
  employee_id            BigInt?
  origin_id              String?             @unique
  origin_data            String?             @db.Text
  synced                 Boolean             @default(false)
  has_workflows          Boolean             @default(false)
  currency_configuration Json?               @db.JsonB
  attachments_s3_keys    Json?               @db.JsonB
  attachment_ids         BigInt[]
  created_at             DateTime            @default(now())
  updated_at             DateTime            @updatedAt
  deleted_at             DateTime?
  last_synced_at         DateTime?
  project                projects            @relation(fields: [project_id], references: [id], onDelete: Cascade)
  vendor                 vendors?            @relation(fields: [vendor_id], references: [id])
  line_items             direct_cost_items[]

  @@index([project_id])
  @@index([vendor_id])
  @@index([origin_id])
  @@index([direct_cost_date])
  @@index([status])
  @@index([last_synced_at])
}

model direct_cost_items {
  id                     BigInt       @id
  direct_cost_id         BigInt
  project_id             BigInt
  wbs_code_id            BigInt?
  cost_code_id           BigInt?
  line_item_type_id      BigInt?
  amount                 Decimal      @db.Decimal(15, 2)
  quantity               Decimal?     @db.Decimal(15, 4)
  unit_cost              Decimal?     @db.Decimal(15, 4)
  uom                    String?
  description            String?      @db.Text
  extended_type          String?
  extended_amount        Decimal?     @db.Decimal(15, 2)
  total_amount           Decimal?     @db.Decimal(15, 2)
  position               Int?
  ref                    String?
  tax_code_id            BigInt?
  origin_id              String?      @unique
  origin_data            String?      @db.Text
  currency_configuration Json?        @db.JsonB
  cost_code              Json?        @db.JsonB
  line_item_type         Json?        @db.JsonB
  wbs_code               Json?        @db.JsonB
  created_at             DateTime     @default(now())
  updated_at             DateTime     @updatedAt
  last_synced_at         DateTime?
  direct_cost            direct_costs @relation(fields: [direct_cost_id], references: [id], onDelete: Cascade)

  @@index([direct_cost_id])
  @@index([project_id])
  @@index([wbs_code_id])
  @@index([origin_id])
  @@index([last_synced_at])
}
