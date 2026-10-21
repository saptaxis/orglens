;;; orglens-test.el --- Tests for orglens.el -*- lexical-binding: t; -*-

;; Run batch and bare, never against a person's Emacs:
;;   Emacs -Q --batch -L emacs -l tests/emacs/orglens-test.el \
;;     -f ert-run-tests-batch-and-exit
;; `tests/test_emacs.py' runs it with the Python suite.  Every test reads a
;; fixture cache in a temporary folder, with `ORGLENS_CONFIG' pointing
;; there, and no refresh starts: the real cache and roots are never read.

;;; Code:

(require 'ert)
(require 'cl-lib)
(require 'json)
(require 'orglens)

(defun orglens-test--json (root)
  "A snapshot of three units under ROOT, a truename, as JSON."
  (let ((p (lambda (rel) (expand-file-name rel root))))
    (json-encode
     `((units
        . [((name . "personal") (aliases . []) (kind . "organization") (part_of . nil)
            (declared_at . ,(funcall p "inwit/personal")) (status . "Mine")
            (homes . [,(funcall p "inwit/personal")])
            (drivers . [((name . "overview") (path . ,(funcall p "inwit/personal/overview.org"))
                         (title . "Personal"))])
            (files . ((doc . [((path . ,(funcall p "inwit/personal/backlog.org"))
                               (title . "Personal backlog"))]))))
           ((name . "scoped-agent-dispatch") (aliases . ["scad"]) (kind . "project")
            (part_of . "personal")
            (declared_at . ,(funcall p "inwit/personal/projects/scad"))
            (status . "Shipping 0.10")
            (homes . [,(funcall p "code/scoped-agent-dispatch")
                      ,(funcall p "inwit/personal/projects/scad")])
            (drivers . [((name . "overview")
                         (path . ,(funcall p "inwit/personal/projects/scad/overview.org"))
                         (title . "scad"))])
            (files . ((spec . [((path . ,(funcall p "inwit/personal/projects/scad/specs/memos.org"))
                                (title . "Memos"))])
                      (doc . [((path . ,(funcall p "inwit/personal/projects/scad/specs/memos.org"))
                               (title . "Memos"))
                              ((path . ,(funcall p "code/scoped-agent-dispatch/README.md"))
                               (title . "scad"))]))))
           ((name . "shared-b") (aliases . []) (kind . "project") (part_of . "loop-a")
            (declared_at . nil) (status . nil)
            (homes . [,(funcall p "code/shared")]) (drivers . []) (files . nil))
           ((name . "shared-a") (aliases . []) (kind . "project") (part_of . "shared-b")
            (declared_at . nil) (status . nil)
            (homes . [,(funcall p "code/shared")]) (drivers . []) (files . nil))
           ((name . "loop-a") (aliases . []) (kind . "project") (part_of . "shared-a")
            (declared_at . nil) (status . nil)
            (homes . [,(funcall p "code/loop")]) (drivers . []) (files . nil))])))))

(defmacro orglens-test--with-cache (root &rest body)
  "Run BODY with a fixture cache; ROOT is bound to the fixture's truename.
No refresh process starts; `orglens-test--spawned' records what would have."
  (declare (indent 1))
  `(let* ((,root (file-name-as-directory (file-truename (make-temp-file "orglens" t))))
          (default-directory ,root)
          (process-environment (cons (concat "ORGLENS_CONFIG=" ,root "config.yaml")
                                     process-environment))
          (orglens--data nil) (orglens--read-from nil) (orglens--said-missing nil)
          (orglens--refreshed-at 0)
          (orglens-refresh nil))
     (unwind-protect
         (progn
           (make-directory (expand-file-name "cache" ,root))
           (with-temp-file (expand-file-name "cache/snapshot.json" ,root)
             (insert (orglens-test--json ,root)))
           ,@body)
       (delete-directory ,root t))))

(defun orglens-test--names (units)
  (mapcar (lambda (u) (plist-get u :name)) units))

(ert-deftest orglens-test-units-come-by-name-as-plists ()
  (orglens-test--with-cache root
    (should (equal (orglens-test--names (orglens-units))
                   '("loop-a" "personal" "scoped-agent-dispatch" "shared-a" "shared-b")))
    (let ((scad (orglens-unit "scoped-agent-dispatch")))
      (should (equal (plist-get scad :kind) "project"))
      (should (equal (plist-get scad :part-of) "personal"))
      (should (equal (plist-get scad :status) "Shipping 0.10"))
      (should (equal (plist-get scad :dir)
                     (expand-file-name "inwit/personal/projects/scad/" root))))))

(ert-deftest orglens-test-a-unit-is-found-by-an-alias ()
  (orglens-test--with-cache root
    (should (equal (plist-get (orglens-unit "scad") :name) "scoped-agent-dispatch"))
    (should (equal (orglens-unit-homes "scad")
                   (list (expand-file-name "code/scoped-agent-dispatch/" root)
                         (expand-file-name "inwit/personal/projects/scad/" root))))
    (should-not (orglens-unit "nobody"))))

(ert-deftest orglens-test-the-nearest-marker-above-a-file-wins ()
  (orglens-test--with-cache root
    ;; Both markers are above it; scad's is nearer.
    (should (equal (plist-get (orglens-unit-at
                               (expand-file-name "inwit/personal/projects/scad/x.org" root))
                              :name)
                   "scoped-agent-dispatch"))
    (should (equal (plist-get (orglens-unit-at
                               (expand-file-name "inwit/personal/inbox.org" root))
                              :name)
                   "personal"))))

(ert-deftest orglens-test-a-file-in-a-code-repository-finds-its-unit-by-home ()
  (orglens-test--with-cache root
    (should (equal (plist-get (orglens-unit-at
                               (expand-file-name "code/scoped-agent-dispatch/src/a.py" root))
                              :name)
                   "scoped-agent-dispatch"))
    (should-not (orglens-unit-at (expand-file-name "elsewhere/a.py" root)))))

(ert-deftest orglens-test-a-shared-home-answers-the-first-by-name-and-lists-all ()
  (orglens-test--with-cache root
    (let ((file (expand-file-name "code/shared/a.py" root)))
      ;; As `orglens where': with no marker above, the first unit by name
      ;; with a home holding it.
      (should (equal (plist-get (orglens-unit-at file) :name) "shared-a"))
      (should (equal (orglens-test--names (orglens-units-at file))
                     '("shared-a" "shared-b"))))))

(ert-deftest orglens-test-a-path-spelled-through-a-symlink-is-resolved ()
  (orglens-test--with-cache root
    (let ((link (make-temp-name (expand-file-name "orglens-link" temporary-file-directory))))
      (unwind-protect
          (progn
            (make-symbolic-link (expand-file-name "code" root) link)
            (should (equal (plist-get (orglens-unit-at
                                       (expand-file-name "scoped-agent-dispatch/a.py" link))
                                      :name)
                           "scoped-agent-dispatch")))
        (delete-file link)))))

(ert-deftest orglens-test-parents-and-children-by-part-of ()
  (orglens-test--with-cache root
    (should (equal (orglens-test--names (orglens-unit-above "scad")) '("personal")))
    (should (equal (orglens-test--names (orglens-unit-and-below "personal"))
                   '("personal" "scoped-agent-dispatch")))
    ;; A cycle stops rather than looping.
    (should (equal (orglens-test--names (orglens-unit-above "shared-a"))
                   '("shared-b" "loop-a")))))

(ert-deftest orglens-test-files-by-unit-and-kind ()
  (orglens-test--with-cache root
    (let ((memos (expand-file-name "inwit/personal/projects/scad/specs/memos.org" root))
          (readme (expand-file-name "code/scoped-agent-dispatch/README.md" root)))
      (should (equal (orglens-files :unit "scad" :kind "spec") (list memos)))
      (should (equal (orglens-files :unit "scad" :kind 'spec) (list memos)))
      (should (equal (orglens-files :unit "scad") (list memos readme)))
      (should (equal (orglens-files :unit "scad" :kind "driver")
                     (list (expand-file-name "inwit/personal/projects/scad/overview.org" root))))
      (should (equal (orglens-files :unit '("personal" "scad") :kind "driver")
                     (list (expand-file-name "inwit/personal/overview.org" root)
                           (expand-file-name "inwit/personal/projects/scad/overview.org" root))))
      (should (= (length (orglens-files)) 3))
      (should (equal (orglens-title memos) "Memos"))
      (should-not (orglens-title (expand-file-name "unlisted.org" root))))))

(ert-deftest orglens-test-the-cache-is-reread-only-when-it-changes ()
  (orglens-test--with-cache root
    (should (orglens-unit "scad"))
    (let ((file (expand-file-name "cache/snapshot.json" root)))
      (with-temp-file file (insert "{\"units\": []}"))
      (set-file-times file (time-add (current-time) 5))
      (should-not (orglens-unit "scad")))))

(ert-deftest orglens-test-no-cache-is-an-empty-answer-said-once ()
  (orglens-test--with-cache root
    (delete-file (expand-file-name "cache/snapshot.json" root))
    (let ((said nil))
      (cl-letf (((symbol-function 'message)
                 (lambda (fmt &rest args) (push (apply #'format fmt args) said))))
        (should-not (orglens-units))
        (should-not (orglens-units)))
      (should (= (length said) 1))
      (should (string-match-p "no snapshot" (car said))))))

(ert-deftest orglens-test-a-read-starts-one-refresh-and-never-waits ()
  (orglens-test--with-cache root
    (let ((orglens-refresh t) (calls nil))
      (cl-letf (((symbol-function 'executable-find) (lambda (_) "/bin/orglens"))
                ((symbol-function 'start-process)
                 (lambda (&rest args) (push args calls) nil))
                ((symbol-function 'set-process-query-on-exit-flag) #'ignore))
        (orglens-units)
        (orglens-units))
      (should (equal calls '(("orglens-refresh" nil "orglens" "snapshot" "--if-stale")))))))

(ert-deftest orglens-test-no-orglens-on-the-path-starts-nothing ()
  (orglens-test--with-cache root
    (let ((orglens-refresh t) (exec-path nil) (calls nil))
      (cl-letf (((symbol-function 'start-process)
                 (lambda (&rest args) (push args calls) nil)))
        (should (orglens-units)))
      (should-not calls))))

(ert-deftest orglens-test-which-unit-names-the-unit-and-its-home ()
  (orglens-test--with-cache root
    (let ((said nil))
      (cl-letf (((symbol-function 'message)
                 (lambda (fmt &rest args) (setq said (apply #'format fmt args)))))
        (orglens-which-unit (expand-file-name "code/scoped-agent-dispatch/a.py" root)))
      (should (string-match-p "scoped-agent-dispatch (project), home .*code/scoped-agent-dispatch/ -- Shipping 0.10"
                              said)))))

(ert-deftest orglens-test-find-document-opens-the-chosen-one ()
  (orglens-test--with-cache root
    (let ((opened nil))
      (cl-letf (((symbol-function 'completing-read)
                 (lambda (_prompt choices &rest _)
                   (seq-find (lambda (c) (string-prefix-p "spec" c)) (mapcar #'car choices))))
                ((symbol-function 'find-file) (lambda (f) (setq opened f))))
        (orglens-find-document "scoped-agent-dispatch"))
      (should (equal opened
                     (expand-file-name "inwit/personal/projects/scad/specs/memos.org" root))))))

(ert-deftest orglens-test-find-unit-opens-its-driver ()
  (orglens-test--with-cache root
    (let ((opened nil))
      (cl-letf (((symbol-function 'completing-read) (lambda (&rest _) "scad"))
                ((symbol-function 'find-file) (lambda (f) (setq opened f))))
        (call-interactively #'orglens-find-unit))
      (should (equal opened
                     (expand-file-name "inwit/personal/projects/scad/overview.org" root))))))

;;; orglens-test.el ends here
