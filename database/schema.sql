CREATE DATABASE IF NOT EXISTS upload_file CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE upload_file;

-- ================= USERS =================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email)
);

-- ================= TAGS =================
CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tag_name (name)
);

-- ================= DOCUMENTS =================
CREATE TABLE documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    description TEXT,
    visibility ENUM('public','private') DEFAULT 'private',
    status VARCHAR(50) DEFAULT 'uploaded',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    user_id INT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    --  INDEXES
    INDEX idx_user_id (user_id),
    INDEX idx_visibility (visibility),
    INDEX idx_filename (filename),
    FULLTEXT INDEX ft_description (description)
);

-- ================= DOCUMENT_TAGS (N-N) =================
CREATE TABLE document_tags (
    document_id INT NOT NULL,
    tag_id INT NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    INDEX idx_doc_id (document_id),
    INDEX idx_tag_id (tag_id)
);

CREATE TABLE user_favorites (
    user_id INT NOT NULL,
    document_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, document_id),
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    
    INDEX idx_user_fav (user_id),
    INDEX idx_doc_fav (document_id)
);

CREATE TABLE user_document_views (
    user_id INT NOT NULL,
    document_id INT NOT NULL,
    
    last_viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, document_id),
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,

    INDEX idx_user_views (user_id, last_viewed_at DESC)
);