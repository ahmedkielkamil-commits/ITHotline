-- ============================================================
-- Lakewood IT Hotline — MySQL Schema + Local Dev Seed Data
-- Notes:
--   * All password columns store bcrypt hashes, NEVER plaintext.
--   * POINT columns use SRID 4326 (GPS lat/long) so
--     ST_Distance_Sphere returns meters.
--   * match_anchor is an approximate, self-chosen area pin used
--     ONLY for distance matching; never returned to any client.
--   * Nullable ticket columns represent lifecycle stages that
--     don't exist at creation (unclaimed, not yet completed).
-- Seed anchor: downtown Atlanta / Luckie St NW (30303 ~33.759, -84.3925)
-- ============================================================

CREATE DATABASE IF NOT EXISTS `ithotline`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `ithotline`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `photos`;
DROP TABLE IF EXISTS `messages`;
DROP TABLE IF EXISTS `ticket`;
DROP TABLE IF EXISTS `admins`;
DROP TABLE IF EXISTS `ITWorker`;
DROP TABLE IF EXISTS `businesses`;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `businesses` (
    `businessid`    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `name`          VARCHAR(255) NOT NULL,
    `password`      VARCHAR(255) NOT NULL,  -- bcrypt hash
    `address`       VARCHAR(255) NOT NULL,
    `email`         VARCHAR(255) NOT NULL UNIQUE,
    `type`          ENUM('market','restaurant','gas_station','barbershop','church','daycare','auto','other') NOT NULL,
    `status`        ENUM('pending','approved','suspended') NOT NULL DEFAULT 'pending',
    `location`      POINT NOT NULL SRID 4326,  -- geocoded at approval
    SPATIAL INDEX `idx_businesses_location` (`location`)
);

CREATE TABLE `ITWorker` (
    `itid`                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `fname`                  VARCHAR(255) NOT NULL,
    `lname`                  VARCHAR(255) NOT NULL,
    `email`                  VARCHAR(255) NOT NULL UNIQUE,
    `phone`                  VARCHAR(20) NULL UNIQUE,   -- E.164 for Twilio SMS dispatch/claim
    `password`               VARCHAR(255) NOT NULL,  -- bcrypt hash
    `status`                 ENUM('pending','approved','suspended') NOT NULL DEFAULT 'pending',
    `tier`                   ENUM('shadow','practitioner') NOT NULL DEFAULT 'shadow',
    `availability`           BOOLEAN NOT NULL DEFAULT FALSE,  -- "taking calls" toggle
    `avail_start_time`       TIME NULL,   -- optional daily window
    `avail_end_time`         TIME NULL,
    `service_radius_m`       INT NOT NULL DEFAULT 8000,
    `vouched_by_name`        VARCHAR(255) NULL,
    `vouched_by_relationship` VARCHAR(255) NULL,
    `skills`                 JSON NULL,   -- e.g. ["pos","network","cameras"]
    `match_anchor`           POINT NOT NULL SRID 4326,  -- approximate area pin; matching only, never exposed
    SPATIAL INDEX `idx_itworker_anchor` (`match_anchor`)
);

CREATE TABLE `admins` (
    `adminid`   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `fname`     VARCHAR(255) NOT NULL,
    `lname`     VARCHAR(255) NOT NULL,
    `email`     VARCHAR(255) NOT NULL UNIQUE,
    `password`  VARCHAR(255) NOT NULL  -- bcrypt hash
);

CREATE TABLE `ticket` (
    `ticketid`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `businessid`         BIGINT UNSIGNED NOT NULL,
    `itid`               BIGINT UNSIGNED NULL,  -- NULL until claimed
    `type`               ENUM('pos','network','cameras','equipment','other') NOT NULL,
    `severity`           ENUM('urgent','standard') NOT NULL,
    `status`             ENUM('open','claimed','en_route','on_site','complete','confirmed','cancelled') NOT NULL DEFAULT 'open',
    `problemReport`      TEXT NOT NULL,
    `created_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `claimed_at`         DATETIME NULL,
    `arrival_time`       DATETIME NULL,
    `completion_time`    DATETIME NULL,
    `completionReport`   TEXT NULL,           -- tech's written work summary
    `amount_charged`     DECIMAL(8,2) NULL,   -- logged at close-out
    `business_confirmed` DATETIME NULL,       -- owner's confirmation (flag + timestamp)
    `business_rating`    TINYINT NULL,        -- thumbs: 1 up / 0 down
    `provider_rating`    TINYINT NULL,
    `cancelReason`       VARCHAR(255) NULL,
    INDEX `idx_ticket_status` (`status`),
    INDEX `idx_ticket_business` (`businessid`),
    INDEX `idx_ticket_worker` (`itid`),
    CONSTRAINT `ticket_businessid_foreign` FOREIGN KEY (`businessid`) REFERENCES `businesses` (`businessid`),
    CONSTRAINT `ticket_itid_foreign` FOREIGN KEY (`itid`) REFERENCES `ITWorker` (`itid`)
);

CREATE TABLE `messages` (
    `messageid`   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `ticketid`    BIGINT UNSIGNED NOT NULL,
    `sendertype`  ENUM('business','provider') NOT NULL,
    `content`     TEXT NOT NULL,
    `send_time`   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `read_time`   DATETIME NULL,  -- NULL = unread
    INDEX `idx_messages_ticket` (`ticketid`),
    CONSTRAINT `messages_ticketid_foreign` FOREIGN KEY (`ticketid`) REFERENCES `ticket` (`ticketid`)
);

CREATE TABLE `photos` (
    `photoid`     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `ticketid`    BIGINT UNSIGNED NOT NULL,
    `upload_type` ENUM('problem','completion') NOT NULL,
    `miniokey`    VARCHAR(255) NOT NULL,  -- object key in MinIO; metadata-pointer pattern
    `upload_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_photos_ticket` (`ticketid`),
    CONSTRAINT `photos_ticketid_foreign` FOREIGN KEY (`ticketid`) REFERENCES `ticket` (`ticketid`)
);

-- ============================================================
-- Seed data (local development)
-- All seed accounts use password: password123 (stored as bcrypt hash below)
-- ============================================================

-- Seed bcrypt hash for password: password123
SET @pw = 'password123';

INSERT INTO `businesses` (`businessid`, `name`, `password`, `address`, `email`, `type`, `status`, `location`) VALUES
(1, 'Luckie Street Grocery Store',              @pw, '265 Luckie St NW, Atlanta, GA 30313',           'lakewood.market@example.com',      'market',      'approved',  ST_GeomFromText('POINT(-84.3964223 33.765137)', 4326)),
(2, 'Atlanta Breakfast Club',                   @pw, '874 Joseph E. Lowery Boulevard Northwest',          'soulkitchen@example.com',          'restaurant',  'approved',  ST_GeomFromText('POINT(-84.4175548 33.7785189)', 4326)),
(3, 'Circle K',                                 @pw, '122 Luckie St NW, Atlanta, GA 30303',           'memorial.exxon@example.com',       'gas_station', 'approved',  ST_GeomFromText('POINT(-84.3900083 33.7595978)', 4326)),
(4, 'Classic Intown Barbershop & MEN Spa',      @pw, '84 Peachtree St NW, Atlanta, GA 30303',        'downtowncuts@example.com',         'barbershop',  'approved',  ST_GeomFromText('POINT(-84.3915795 33.7561944)', 4326)),
(5, 'Atlanta First United Methodist Church',    @pw, '360 Peachtree St NE, Atlanta, GA 30308',        'office@ebenezercomm.example.com',  'church',      'approved',  ST_GeomFromText('POINT(-84.3861581 33.7642809)', 4326)),
(6, 'Peach Mart',                               @pw, '130 Luckie St NW, Atlanta, GA 30303',           'director@sweetauburn.example.com', 'daycare',     'approved',  ST_GeomFromText('POINT(-84.3882529 33.7599132)', 4326)),
(7, 'Main Street Auto',                         @pw, '191 Peachtree St, Atlanta, GA 30303',          'service@grantparkauto.example.com','auto',        'pending',   ST_GeomFromText('POINT(-84.3868148 33.7589822)', 4326)),
(8, 'The Food Shoppe',                          @pw, '122 Luckie St NW, Atlanta, GA 30303',           'info@fwprint.example.com',         'other',       'suspended', ST_GeomFromText('POINT(-84.3904342 33.7583101)', 4326)),
(9, 'Brawley Street Market',                    @pw, '111 James P Brawley Dr SW, Atlanta, GA 30314',  'brawley.market@example.com',       'market',      'approved',  ST_GeomFromText('POINT(-84.4135506 33.7515371)', 4326));

INSERT INTO `ITWorker` (`itid`, `fname`, `lname`, `email`, `phone`, `password`, `status`, `tier`, `availability`, `avail_start_time`, `avail_end_time`, `service_radius_m`, `vouched_by_name`, `vouched_by_relationship`, `skills`, `match_anchor`) VALUES
(1, 'Marcus',  'Johnson',  'marcus.johnson@example.com',  '+14045550101', @pw, 'approved', 'practitioner', TRUE,  '08:00:00', '18:00:00',  8000, 'Rev. James Holloway', 'pastor at Atlanta First United Methodist Church', '["pos","network"]',                 ST_GeomFromText('POINT(-84.3925 33.7590)', 4326)),
(2, 'Denise',  'Williams', 'denise.williams@example.com', '+14045550102', @pw, 'approved', 'practitioner', FALSE, '09:00:00', '17:00:00', 12000, 'Tanya Brooks',        'owner of Luckie Street Grocery Store',            '["cameras","network","equipment"]', ST_GeomFromText('POINT(-84.3940 33.7610)', 4326)),
(3, 'Terrell', 'Brooks',   'terrell.brooks@example.com',  '+14045550103', @pw, 'approved', 'practitioner', TRUE,  '07:30:00', '19:30:00', 10000, 'Carlos Mendez',       'manager at Circle K',                             '["pos","equipment"]',               ST_GeomFromText('POINT(-84.3895 33.7585)', 4326)),
(4, 'Aisha',   'Patel',    'aisha.patel@example.com',     '+14045550104', @pw, 'approved', 'shadow',       TRUE,  '10:00:00', '16:00:00',  5000, 'Marcus Johnson',      'existing IT Hotline provider',                    '["network","other"]',               ST_GeomFromText('POINT(-84.3910 33.7605)', 4326)),
(5, 'James',   'Okafor',   'james.okafor@example.com',    '+14045550105', @pw, 'approved', 'practitioner', FALSE, '08:30:00', '20:00:00', 15000, 'Denise Williams',     'existing IT Hotline provider',                    '["cameras","pos","network"]',       ST_GeomFromText('POINT(-84.3875 33.7575)', 4326)),
(6, 'Carmen',  'Ruiz',     'carmen.ruiz@example.com',     NULL,           @pw, 'pending',  'shadow',       FALSE, NULL,       NULL,        7500, 'Rev. James Holloway', 'pastor at Atlanta First United Methodist Church', '["equipment","other"]',             ST_GeomFromText('POINT(-84.3855 33.7635)', 4326)),
(7, 'Keisha',  'Williams', 'keisha.williams@example.com', '+14045550107', @pw, 'approved', 'practitioner', TRUE,  '08:00:00', '18:00:00', 10000, 'Brawley Street Market', 'neighbor business on James P Brawley Dr SW',      '["pos","network","equipment"]',     ST_GeomFromText('POINT(-84.4135506 33.7515371)', 4326));

INSERT INTO `admins` (`adminid`, `fname`, `lname`, `email`, `password`) VALUES
(1, 'Angela', 'Reed',   'angela.reed@ithotline.example.com',  @pw),
(2, 'David',  'Nguyen', 'david.nguyen@ithotline.example.com', @pw),
(3, 'Priya',  'Sharma', 'priya.sharma@ithotline.example.com', @pw);

INSERT INTO `ticket` (
    `ticketid`, `businessid`, `itid`, `type`, `severity`, `status`, `problemReport`,
    `created_at`, `claimed_at`, `arrival_time`, `completion_time`,
    `completionReport`, `amount_charged`, `business_confirmed`,
    `business_rating`, `provider_rating`, `cancelReason`
) VALUES
(1,  1, NULL, 'pos',       'urgent',   'open',      'Register 2 keeps freezing during lunch rush. Screen goes white and we cannot ring up customers.',
 '2026-07-20 09:00:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(2,  2, NULL, 'network',   'standard', 'open',      'Wi-Fi drops every afternoon around 3 PM. Kitchen tablets lose connection to the order system.',
 '2026-07-20 10:30:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(3,  3, 1,    'cameras',   'urgent',   'claimed',   'Two pumps are not visible on the security monitor after last night''s storm. Need eyes on the lot ASAP.',
 '2026-07-19 08:00:00', '2026-07-19 08:45:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(4,  4, 2,    'equipment', 'standard', 'en_route',  'Receipt printer jammed and now will not print at all. Customers waiting on paper receipts.',
 '2026-07-19 11:00:00', '2026-07-19 11:22:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(5,  5, 3,    'network',   'urgent',   'on_site',   'Office router blinking red. Cannot access donation portal or email for Sunday service prep.',
 '2026-07-18 14:00:00', '2026-07-18 14:28:00', '2026-07-18 15:05:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(6,  6, 4,    'pos',       'standard', 'complete',  'Check-in kiosk for parents shows a blank screen every morning until someone reboots it manually.',
 '2026-07-17 09:00:00', '2026-07-17 09:35:00', '2026-07-17 10:10:00', '2026-07-17 11:40:00',
 'Replaced failing USB hub and updated kiosk drivers. Ran 30-min soak test with no blank screen recurrence.',
 125.00, NULL, NULL, NULL, NULL),

(7,  1, 1,    'network',   'standard', 'confirmed', 'Back-office PC cannot reach inventory scanner. Ethernet light is amber.',
 '2026-07-15 08:30:00', '2026-07-15 09:00:00', '2026-07-15 09:45:00', '2026-07-15 10:30:00',
 'Re-terminated loose patch cable and reset switch port. Scanner back online and tested with 10 sample scans.',
 89.50, '2026-07-15 14:00:00', 1, 1, NULL),

(8,  2, 2,    'cameras',   'urgent',   'confirmed', 'Back door camera offline since Friday. Cannot review overnight footage.',
 '2026-07-14 07:15:00', '2026-07-14 07:50:00', '2026-07-14 08:30:00', '2026-07-14 09:55:00',
 'Replaced PoE injector and re-paired camera to NVR. Verified 48 hrs of recording buffer restored.',
 175.00, '2026-07-14 16:30:00', 1, 1, NULL),

(9,  3, 3,    'pos',       'standard', 'confirmed', 'Pump 4 card reader intermittently declines valid cards.',
 '2026-07-12 13:00:00', '2026-07-12 13:40:00', '2026-07-12 14:15:00', '2026-07-12 15:20:00',
 'Cleaned card reader contacts and pushed firmware update from vendor portal. Ran 20 test swipes successfully.',
 65.00, '2026-07-12 18:00:00', 1, 0, NULL),

(10, 4, 5,    'equipment', 'standard', 'confirmed', 'Waiting-area TV stuck on boot logo. Customers think we are closed.',
 '2026-07-10 10:00:00', '2026-07-10 10:35:00', '2026-07-10 11:10:00', '2026-07-10 12:05:00',
 'Factory reset streaming stick and reconfigured HDMI-CEC. TV now auto-powers on with shop hours schedule.',
 45.00, '2026-07-10 17:00:00', 1, 1, NULL),

(11, 5, NULL, 'other',     'standard', 'cancelled', 'Need help setting up livestream audio for midweek service.',
 '2026-07-16 11:00:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'Resolved internally — volunteer AV team fixed the issue before provider arrived.'),

(12, 6, 5,    'cameras',   'urgent',   'confirmed', 'Playground camera feed not showing on director''s phone app. Safety concern during pickup.',
 '2026-07-08 15:30:00', '2026-07-08 16:00:00', '2026-07-08 16:35:00', '2026-07-08 17:50:00',
 'Updated camera firmware and re-linked mobile app credentials. Verified live view on two staff phones.',
 210.00, '2026-07-08 19:00:00', 1, 1, NULL);

INSERT INTO `messages` (`messageid`, `ticketid`, `sendertype`, `content`, `send_time`, `read_time`) VALUES
(1,  3, 'business',  'Cameras on pumps 3 and 4 are completely black. Can you come today?',           '2026-07-19 08:05:00', '2026-07-19 08:20:00'),
(2,  3, 'provider',  'On my way — ETA 25 minutes. I will bring a spare PoE adapter just in case.',   '2026-07-19 08:22:00', NULL),
(3,  4, 'business',  'Printer is totally dead. We are handwriting receipts right now.',              '2026-07-19 11:05:00', '2026-07-19 11:15:00'),
(4,  4, 'provider',  'Claimed your ticket. Heading over from Luckie Street now.',                    '2026-07-19 11:25:00', NULL),
(5,  5, 'business',  'Router has been red since noon. We have a board meeting in two hours.',        '2026-07-18 14:05:00', '2026-07-18 14:15:00'),
(6,  5, 'provider',  'Just arrived. Checking the modem and switch in the office closet.',          '2026-07-18 15:08:00', '2026-07-18 15:10:00'),
(7,  6, 'business',  'Parents are lining up and the kiosk is blank again.',                          '2026-07-17 09:05:00', '2026-07-17 09:20:00'),
(8,  6, 'provider',  'Found a bad USB hub. Replacing it now — should be back up in 10 minutes.',     '2026-07-17 10:15:00', NULL),
(9,  7, 'business',  'Scanner still amber after reboot. We cannot receive this morning''s delivery.', '2026-07-15 08:35:00', '2026-07-15 08:50:00'),
(10, 7, 'provider',  'Loose patch cable at the switch. Fixed and tested — you are good to scan.',    '2026-07-15 10:35:00', '2026-07-15 10:40:00'),
(11, 8, 'business',  'No footage from back door since Friday night. This is urgent for us.',         '2026-07-14 07:20:00', '2026-07-14 07:35:00'),
(12, 8, 'provider',  'PoE injector failed. Installing replacement now.',                             '2026-07-14 08:35:00', '2026-07-14 08:40:00'),
(13, 9, 'business',  'Pump 4 declined three cards in a row this hour.',                              '2026-07-12 13:05:00', '2026-07-12 13:20:00'),
(14, 9, 'provider',  'Firmware update applied. Please try a test transaction when you can.',         '2026-07-12 15:25:00', NULL),
(15, 10, 'business', 'TV has been stuck on the logo all morning. Can someone look at it?',           '2026-07-10 10:05:00', '2026-07-10 10:15:00'),
(16, 10, 'provider', 'Streaming stick reset and reconfigured. Should boot normally now.',            '2026-07-10 12:10:00', '2026-07-10 12:15:00'),
(17, 12, 'business', 'Playground camera not on the app. Parents are asking about pickup safety.',   '2026-07-08 15:35:00', '2026-07-08 15:50:00'),
(18, 12, 'provider', 'Camera firmware updated and app re-linked. Please confirm you see live view.', '2026-07-08 17:55:00', NULL);

INSERT INTO `photos` (`photoid`, `ticketid`, `upload_type`, `miniokey`, `upload_time`) VALUES
(1, 3,  'problem',    'tickets/3/problem_1.jpg',     '2026-07-19 08:10:00'),
(2, 4,  'problem',    'tickets/4/problem_1.jpg',     '2026-07-19 11:08:00'),
(3, 5,  'problem',    'tickets/5/problem_1.jpg',     '2026-07-18 14:08:00'),
(4, 6,  'problem',    'tickets/6/problem_1.jpg',     '2026-07-17 09:08:00'),
(5, 6,  'completion', 'tickets/6/completion_1.jpg',  '2026-07-17 11:42:00'),
(6, 8,  'problem',    'tickets/8/problem_1.jpg',     '2026-07-14 07:25:00'),
(7, 8,  'completion', 'tickets/8/completion_1.jpg',  '2026-07-14 09:58:00'),
(8, 12, 'completion', 'tickets/12/completion_1.jpg', '2026-07-08 17:52:00');
