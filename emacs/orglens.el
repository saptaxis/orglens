;;; orglens.el --- Units of work, from orglens -*- lexical-binding: t; -*-

;; Author: Vignesh Saptarishi
;; URL: https://github.com/saptaxis/orglens
;; Version: 0.8.0
;; Package-Requires: ((emacs "29.1"))
;; Keywords: outlines, files, tools

;;; Commentary:

;; What orglens knows, in Emacs: the units, their homes, and their
;; documents with their titles.  Read from orglens's cache,
;; `~/.orglens/cache/snapshot.json' (beside the config `ORGLENS_CONFIG'
;; names, when it is set), never by scanning the tree.
;;
;; Each read starts `orglens snapshot --if-stale' in the background and
;; answers from the cache it has: an answer is at most one read behind, and
;; nothing waits.
;;
;; Functions first.  A unit is a plist: :name :aliases :kind :part-of :dir
;; (the folder of its marker) :status :homes.  What a person builds from
;; them -- agenda files, perspectives, capture targets -- is theirs; the
;; three commands are thin, and bind no keys.
;;
;;   (orglens-units)                    every unit
;;   (orglens-unit NAME)                by name or alias
;;   (orglens-unit-homes NAME)          its homes
;;   (orglens-unit-at FILE)             the unit FILE belongs to
;;   (orglens-units-at FILE)            every unit with a home holding FILE
;;   (orglens-unit-above NAME)          its parents by part_of, nearest first
;;   (orglens-unit-and-below NAME)      it and every unit under it
;;   (orglens-files :unit U :kind K)    document paths; K may be "driver"
;;   (orglens-title FILE)               a listed document's title

;;; Code:

(require 'cl-lib)
(require 'seq)
(require 'subr-x)

(defgroup orglens nil
  "Units of work, from orglens."
  :group 'tools
  :prefix "orglens-")

(defcustom orglens-program "orglens"
  "The orglens command."
  :type 'string)

(defcustom orglens-refresh t
  "Whether a read starts `orglens snapshot --if-stale' in the background."
  :type 'boolean)

(defvar orglens--data nil
  "The units read from the cache, as plists.")

(defvar orglens--read-from nil
  "The cache file and its modification time when `orglens--data' was read.")

(defvar orglens--said-missing nil
  "Whether the missing cache has been reported, so it is said once.")

(defvar orglens--refreshed-at 0
  "When a refresh was last started, as a float time.")

(defconst orglens--refresh-every 10
  "Seconds between refreshes: one command reads the cache many times.")

;;;; The cache

(defun orglens--config-dir ()
  "The folder of the config in force: `ORGLENS_CONFIG''s, else ~/.orglens."
  (if-let* ((config (getenv "ORGLENS_CONFIG"))
            ((not (string-empty-p config))))
      (file-name-directory (expand-file-name config))
    (expand-file-name "~/.orglens/")))

(defun orglens--cache-file ()
  "Where orglens writes the snapshot's data."
  (expand-file-name "cache/snapshot.json" (orglens--config-dir)))

(defun orglens--refresh ()
  "Start `orglens snapshot --if-stale', detached; never wait, never fail.
orglens's lock keeps one refresh at a time."
  (when (and orglens-refresh
             (> (- (float-time) orglens--refreshed-at) orglens--refresh-every)
             (executable-find orglens-program))
    (setq orglens--refreshed-at (float-time))
    (ignore-errors
      (let ((process (start-process "orglens-refresh" nil orglens-program
                                    "snapshot" "--if-stale")))
        (set-process-query-on-exit-flag process nil)))))

(defun orglens--dir (path)
  "PATH as a directory name, symlinks resolved."
  (file-name-as-directory (file-truename path)))

(defun orglens--unit (raw)
  "A unit plist from RAW, one unit of the snapshot's JSON."
  (list :name (plist-get raw :name)
        :aliases (plist-get raw :aliases)
        :kind (plist-get raw :kind)
        :part-of (plist-get raw :part_of)
        :dir (when-let* ((dir (plist-get raw :declared_at))) (orglens--dir dir))
        :status (plist-get raw :status)
        :homes (mapcar #'orglens--dir (plist-get raw :homes))
        :drivers (plist-get raw :drivers)
        :files (plist-get raw :files)))

(defun orglens--read ()
  "The units in the cache, reread only when the file changed."
  (orglens--refresh)
  (let* ((file (orglens--cache-file))
         (mtime (file-attribute-modification-time (file-attributes file))))
    (cond
     ((null mtime)
      (unless orglens--said-missing
        (setq orglens--said-missing t)
        (message "orglens: no snapshot at %s; run `orglens snapshot'" file))
      (setq orglens--data nil orglens--read-from nil))
     ((not (equal orglens--read-from (cons file mtime)))
      (setq orglens--data
            (with-temp-buffer
              (insert-file-contents file)
              (sort (mapcar #'orglens--unit
                            (plist-get (json-parse-buffer :object-type 'plist
                                                          :array-type 'list
                                                          :null-object nil
                                                          :false-object nil)
                                       :units))
                    (lambda (a b) (string< (plist-get a :name) (plist-get b :name)))))
            orglens--read-from (cons file mtime)
            orglens--said-missing nil)))
    orglens--data))

;;;; Units

(defun orglens-units ()
  "Every unit, as plists, by name.  Shared with the cache: copy before
changing it."
  (orglens--read))

(defun orglens-unit (name)
  "The unit called NAME, or answering to it as an alias; its own name first."
  (let ((units (orglens-units)))
    (or (seq-find (lambda (u) (equal (plist-get u :name) name)) units)
        (seq-find (lambda (u) (member name (plist-get u :aliases))) units))))

(defun orglens-unit-homes (name)
  "The homes of the unit NAME, as directory names."
  (plist-get (orglens-unit name) :homes))

(defun orglens--inside (dir file)
  "Whether FILE, a truename, is DIR or under it."
  (string-prefix-p dir (file-name-as-directory file)))

(defun orglens--truename (file)
  "FILE resolved, or the current buffer's file or directory when nil."
  (file-truename (or file buffer-file-name default-directory)))

(defun orglens-unit-at (&optional file)
  "The unit FILE belongs to, as `orglens where' answers it.
Up from FILE to the first marker; with none above (a code repository
carries none), the first unit by name with a home holding FILE.  FILE
defaults to the current buffer's file or directory."
  (let* ((file (orglens--truename file))
         (units (orglens-units))
         (marked (seq-filter (lambda (u) (and (plist-get u :dir)
                                              (orglens--inside (plist-get u :dir) file)))
                             units)))
    (if marked
        (car (sort marked (lambda (a b) (> (length (plist-get a :dir))
                                           (length (plist-get b :dir))))))
      (seq-find (lambda (u) (seq-some (lambda (h) (orglens--inside h file))
                                      (plist-get u :homes)))
                units))))

(defun orglens-units-at (&optional file)
  "Every unit with a home holding FILE, the deepest home first.
A home several units share gives each of them."
  (let* ((file (orglens--truename file))
         (depth (lambda (u)
                  (apply #'max 0 (mapcar (lambda (h) (if (orglens--inside h file) (length h) 0))
                                         (plist-get u :homes))))))
    (sort (seq-filter (lambda (u) (> (funcall depth u) 0)) (orglens-units))
          (lambda (a b) (> (funcall depth a) (funcall depth b))))))

(defun orglens-unit-above (name)
  "The units the unit NAME is part of, its parent first; a cycle stops it."
  (let ((seen (list name)) (out nil)
        (up (plist-get (orglens-unit name) :part-of)))
    (while (and up (not (member up seen)))
      (push up seen)
      (let ((unit (orglens-unit up)))
        (push (or unit (list :name up)) out)
        (setq up (plist-get unit :part-of))))
    (nreverse out)))

(defun orglens-unit-and-below (name)
  "The unit NAME and every unit whose `part_of' leads up to it."
  (when-let* ((top (orglens-unit name)))
    (let ((top-name (plist-get top :name)))
      (cons top
            (seq-filter (lambda (u)
                          (member top-name (mapcar (lambda (p) (plist-get p :name))
                                                   (orglens-unit-above (plist-get u :name)))))
                        (orglens-units))))))

;;;; Documents

(defun orglens--documents (unit kind)
  "UNIT's documents of KIND as (:path :title) plists; KIND nil is every kind."
  (cond
   ((equal kind "driver") (plist-get unit :drivers))
   (kind (plist-get (plist-get unit :files) (intern (concat ":" kind))))
   (t (let ((seen (make-hash-table :test #'equal)) out)
        (cl-loop for (_ docs) on (plist-get unit :files) by #'cddr
                 do (dolist (doc docs)
                      (unless (gethash (plist-get doc :path) seen)
                        (puthash (plist-get doc :path) t seen)
                        (push doc out))))
        (nreverse out)))))

(cl-defun orglens-files (&key unit kind)
  "Document paths: of UNIT (a name, an alias or a list of them; nil for
every unit) and of KIND (a document kind such as \"plan\", or \"driver\"
for the driver document and the others its kind declares; nil for all)."
  (let* ((kind (and kind (format "%s" kind)))
         (units (cond ((null unit) (orglens-units))
                      ((listp unit) (delq nil (mapcar #'orglens-unit unit)))
                      (t (delq nil (list (orglens-unit unit)))))))
    (delete-dups
     (mapcan (lambda (u) (mapcar (lambda (d) (plist-get d :path))
                                 (orglens--documents u kind)))
             units))))

(defun orglens-title (file)
  "The title of FILE, when the snapshot lists it.  The snapshot's paths
are resolved, as FILE is here."
  (let ((file (file-truename file)))
    (cl-loop for unit in (orglens-units)
             thereis (cl-loop for doc in (append (plist-get unit :drivers)
                                                 (orglens--documents unit nil))
                              when (equal (plist-get doc :path) file)
                              return (plist-get doc :title)))))

;;;; Commands

(defun orglens--read-unit (prompt)
  "Ask for a unit by name or alias with PROMPT, its status as the hint."
  (let* ((units (orglens-units))
         (here (plist-get (orglens-unit-at) :name))
         (hint (make-hash-table :test #'equal)))
    (dolist (u units)
      (puthash (plist-get u :name) (or (plist-get u :status) "") hint)
      (dolist (alias (plist-get u :aliases))
        (puthash alias (format "%s: %s" (plist-get u :name) (or (plist-get u :status) ""))
                 hint)))
    (unless units (user-error "orglens: no units; is there a snapshot?"))
    (let ((completion-extra-properties
           (list :annotation-function
                 (lambda (c) (concat "  " (truncate-string-to-width (gethash c hint "") 70))))))
      (plist-get (orglens-unit (completing-read prompt (hash-table-keys hint) nil t
                                                nil nil here))
                 :name))))

;;;###autoload
(defun orglens-find-unit (name)
  "Open the driver document of the unit NAME, or its folder when it has none."
  (interactive (list (orglens--read-unit "Unit: ")))
  (let ((unit (orglens-unit name)))
    (find-file (or (plist-get (car (plist-get unit :drivers)) :path)
                   (plist-get unit :dir)
                   (car (plist-get unit :homes))))))

;;;###autoload
(defun orglens-find-document (name)
  "Open one of the unit NAME's documents, chosen by kind and title."
  (interactive (list (orglens--read-unit "Documents of: ")))
  (let* ((unit (orglens-unit name))
         (choices nil))
    (dolist (doc (plist-get unit :drivers))
      (push (cons (format "driver  %s" (or (plist-get doc :title) (plist-get doc :name)))
                  (plist-get doc :path))
            choices))
    (cl-loop for (key docs) on (plist-get unit :files) by #'cddr
             for kind = (substring (symbol-name key) 1)
             do (dolist (doc docs)
                  (push (cons (format "%-7s %s  %s" kind
                                      (or (plist-get doc :title) "")
                                      (file-name-nondirectory (plist-get doc :path)))
                              (plist-get doc :path))
                        choices)))
    (setq choices (nreverse choices))
    (unless choices (user-error "orglens: %s lists no documents" name))
    (find-file (cdr (assoc (completing-read (format "%s: " name) choices nil t)
                           choices)))))

;;;###autoload
(defun orglens-which-unit (&optional file)
  "Say which unit FILE, or the current buffer, belongs to, and through which home."
  (interactive)
  (let* ((path (orglens--truename file))
         (unit (orglens-unit-at path)))
    (if (not unit)
        (message "orglens: %s is in no unit" (abbreviate-file-name path))
      (let ((home (car (sort (seq-filter (lambda (h) (orglens--inside h path))
                                         (plist-get unit :homes))
                             (lambda (a b) (> (length a) (length b)))))))
        (message "orglens: %s (%s)%s%s" (plist-get unit :name) (plist-get unit :kind)
                 (if home (format ", home %s" (abbreviate-file-name home)) "")
                 (if-let* ((status (plist-get unit :status))) (format " -- %s" status) ""))))))

(provide 'orglens)
;;; orglens.el ends here
