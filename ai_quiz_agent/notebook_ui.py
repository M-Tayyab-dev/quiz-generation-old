"""Interactive Colab interface for the six-stage flow diagram."""
from html import escape
import ipywidgets as w
from IPython.display import display, HTML, clear_output
from .workflow import QuizWorkflow


def launch():
    flow = QuizWorkflow()
    upload = w.FileUpload(accept=".pdf,.docx,.txt", multiple=False, description="Upload notes")
    language = w.Dropdown(options=["English", "Urdu"], description="Language:")
    difficulty = w.Dropdown(options=["easy", "medium", "hard"], value="medium", description="Difficulty:")
    count = w.BoundedIntText(value=5, min=1, max=30, description="MCQs:")
    generate = w.Button(description="Generate quiz", button_style="success")
    history = w.Button(description="View history")
    status, player, results = w.HTML(), w.VBox(), w.Output()
    state = {}

    def progress(message):
        status.value = escape(message)

    def make_quiz(_):
        generate.disabled = True
        player.children = ()
        results.clear_output()
        try:
            if not upload.value:
                raise ValueError("Upload study material first.")
            value = upload.value
            item = next(iter(value.values())) if isinstance(value, dict) else value[0]
            name = item.get("name") or next(iter(value))
            progress("Reading and analyzing document...")
            document = flow.upload(name, bytes(item["content"]))
            quiz = flow.generate(document["document_id"], count.value, difficulty.value,
                                 language=language.value, on_progress=progress)
            state["quiz"] = quiz
            selections = {}
            children = []
            for index, question in enumerate(quiz["questions"], 1):
                children.append(w.HTML(f'<b>{index}. {escape(question["question"])}</b>'))
                selection = w.RadioButtons(options=question["options"], index=None,
                                           layout=w.Layout(width="100%"))
                selections[question["id"]] = selection
                children.append(selection)
            submit = w.Button(description="Submit answers", button_style="primary")

            def finish(_):
                try:
                    answers = {key:widget.value for key,widget in selections.items() if widget.value is not None}
                    report = flow.submit(quiz["quiz_id"], answers)
                    submit.disabled = True
                    for widget in selections.values():
                        widget.disabled = True
                    with results:
                        clear_output()
                        score = report["score"]
                        display(HTML(f'<h3>{score["percentage"]}% · Grade {report["grade"]}</h3>'
                            f'<p>Correct: {score["correct_answers"]} · Incorrect: {score["incorrect_answers"]}'
                            f' · Unanswered: {score["unanswered"]}</p><p>{report["grade_note"]}</p>'))
                        for topic, stats in report["topics"].items():
                            print(f'{topic}: {stats["correct"]}/{stats["total"]} ({stats["percentage"]}%)')
                        for tip in report["recommendations"]:
                            print(tip)
                        for q in report["review"]:
                            display(HTML(f'<hr><b>{escape(q["question"])}</b><p>Your answer: '
                                f'{escape(q["student_answer"] or "Unanswered")}<br>Correct answer: '
                                f'{escape(q["correct_answer"])}</p><p>{escape(q["explanation"])}</p>'
                                f'<blockquote>{escape(q["source_quote"])}</blockquote>'))
                    progress("Results saved. Choose Generate quiz for fresh practice.")
                except Exception as exc:
                    progress(f"Could not submit: {exc}")

            submit.on_click(finish)
            player.children = tuple(children + [submit])
            progress("Quiz ready. Select your answers, then submit.")
        except Exception as exc:
            progress(f"Could not generate quiz: {type(exc).__name__}: {exc}")
        finally:
            generate.disabled = False

    def show_history(_):
        with results:
            clear_output()
            records = flow.history()
            if not records:
                print("No completed quizzes yet.")
            for record in records:
                print(f'{record["score"]["percentage"]}% · {record["grade"]} · {record["quiz_id"]}')

    generate.on_click(make_quiz)
    history.on_click(show_history)
    display(w.VBox([w.HTML('<h2>Document Quiz Practice</h2><p>Upload → Generate → Solve → Review → Improve</p>'
            '<p>PDF, Word (.docx), or TXT · Practice questions based on your notes · Current-affairs accuracy depends on the source date.</p>'),
            upload, language, difficulty, count, w.HBox([generate, history]), status, player, results]))
    return flow
