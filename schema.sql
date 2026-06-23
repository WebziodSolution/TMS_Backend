-- schema.sql
-- Ticket Management System (TMS) Database Schema

CREATE DATABASE IF NOT EXISTS tms;
USE tms;

-- Table: roles
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NULL,
    role_id INT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    zip VARCHAR(20),
    phone VARCHAR(20),
    is_sms_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

-- Table: functionalities
CREATE TABLE IF NOT EXISTS functionalities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Table: modules
CREATE TABLE IF NOT EXISTS modules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    functionality_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    FOREIGN KEY (functionality_id) REFERENCES functionalities(id) ON DELETE CASCADE
);

-- Table: actions
CREATE TABLE IF NOT EXISTS actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Table: modules_actions
CREATE TABLE IF NOT EXISTS modules_actions (
    module_id INT NOT NULL,
    action_id INT NOT NULL,
    PRIMARY KEY (module_id, action_id),
    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
);

-- Table: role_actions
CREATE TABLE IF NOT EXISTS role_actions (
    role_id INT NOT NULL,
    action_id INT NOT NULL,
    PRIMARY KEY (role_id, action_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
);

-- Table: otps
CREATE TABLE IF NOT EXISTS otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    code VARCHAR(10) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Insert roles
INSERT IGNORE INTO roles (id, name) VALUES
(1, 'Administrator'),
(2, 'Developer'),
(3, 'Customer'),
(4, 'Manager');

-- Insert actions
INSERT IGNORE INTO actions (id, name) VALUES
(1, 'Add'),
(2, 'Edit'),
(3, 'Delete'),
(4, 'View');

-- Insert functionalities
INSERT IGNORE INTO functionalities (name) VALUES
('manage user'),
('manage ticket status'),
('manage department'),
('manage tickets'),
('manage project');

-- Let's assign some initial mock mapping for modules based on functionalities for demo purposes
-- Assuming functionality 'manage user' is 1
INSERT IGNORE INTO modules (id, functionality_id, name) VALUES 
(1, 1, 'Users List'),
(2, 4, 'Tickets');

-- Module Actions mapped
INSERT IGNORE INTO modules_actions (module_id, action_id) VALUES
(1, 1), (1, 2), (1, 3), (1, 4),
(2, 1), (2, 2), (2, 3), (2, 4);

-- Role actions base (Admin has all)
INSERT IGNORE INTO role_actions (role_id, action_id) VALUES
(1, 1), (1, 2), (1, 3), (1, 4), -- Admin
(2, 4), (2, 2),                 -- Dev
(3, 4), (3, 1);                 -- Customer

-- Table: status
CREATE TABLE IF NOT EXISTS status (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- Insert module for status and its actions
INSERT IGNORE INTO modules (id, functionality_id, name) 
SELECT 4, id, 'Status List' FROM functionalities WHERE name = 'manage ticket status';

INSERT IGNORE INTO modules_actions (module_id, action_id) VALUES
(4, 1), (4, 2), (4, 3), (4, 4);

ALTER TABLE `modules_actions` ADD `id` INT NOT NULL AUTO_INCREMENT FIRST, ADD PRIMARY KEY (`id`);

-- Table: projects
CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    client_id INT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Insert module for projects and its actions
INSERT IGNORE INTO modules (id, functionality_id, name) 
SELECT 5, id, 'Projects List' FROM functionalities WHERE name = 'manage project';

INSERT IGNORE INTO modules_actions (module_id, action_id) VALUES
(5, 1), (5, 2), (5, 3), (5, 4);

-- Table: tickets
CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date DATETIME,
    as_customer BOOLEAN DEFAULT FALSE,
    for_customer BOOLEAN DEFAULT FALSE,
    created_by INT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Table: assigned_tickets
CREATE TABLE IF NOT EXISTS assigned_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    assign_to INT NOT NULL,
    created_by INT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (assign_to) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Table: tickets_attachments
CREATE TABLE IF NOT EXISTS tickets_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_URL VARCHAR(500) NOT NULL,
    created_by INT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

ALTER TABLE `tickets` ADD `project_id` INT NULL AFTER `id`;

ALTER TABLE `tickets` DROP FOREIGN KEY `tickets_ibfk_1`; ALTER TABLE `tickets` ADD CONSTRAINT `tickets_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users`(`id`) ON DELETE CASCADE ON UPDATE RESTRICT; 
ALTER TABLE `tickets` ADD FOREIGN KEY (`project_id`) REFERENCES `projects`(`id`) ON DELETE CASCADE ON UPDATE RESTRICT;

ALTER TABLE `users` ADD `report_to` INT NULL AFTER `is_active`;
ALTER TABLE `users` ADD FOREIGN KEY (`report_to`) REFERENCES `users`(`id`) ON DELETE SET NULL ON UPDATE RESTRICT;

ALTER TABLE `tickets` ADD `department_id` INT NULL AFTER `project_id`;
ALTER TABLE `tickets` ADD FOREIGN KEY (`department_id`) REFERENCES `departments`(`id`) ON DELETE CASCADE ON UPDATE RESTRICT;

ALTER TABLE `tickets` ADD `ticket_no` VARCHAR(50) NOT NULL AFTER `id`;

-- Table: ticket_comments_type
CREATE TABLE IF NOT EXISTS ticket_comments_type (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    created_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
);

-- Insert ticket_comments_type
INSERT IGNORE INTO ticket_comments_type (id, name) VALUES
(1, 'Open'),
(2, 'Private to Developer'),
(3, 'Private to Customer'),
(4, 'Private to manager'),
(5, 'Private to Admin');
(6, 'Private');

-- Table: ticket_comments
CREATE TABLE IF NOT EXISTS ticket_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    comment LONGTEXT NOT NULL,
    parent_comment_id INT,
    comment_type_id INT,
    created_by INT,
    created_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_comment_id) REFERENCES ticket_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (comment_type_id) REFERENCES ticket_comments_type(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Table: ticket_comments_attachments
CREATE TABLE IF NOT EXISTS ticket_comments_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_comment_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    created_by INT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_comment_id) REFERENCES ticket_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

ALTER TABLE `tickets` ADD `working_hours` VARCHAR(50) NULL AFTER `due_date`;

ALTER TABLE tms.ticket_comments_type DROP FOREIGN KEY ticket_comments_type_ibfk_1;

ALTER TABLE `ticket_comments_type` DROP `created_by`;

ALTER TABLE `projects` ADD `project_type` VARCHAR(100) NULL AFTER `client_id`;