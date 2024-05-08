from django.http import HttpResponse
from web.qa_service import get_answer

from django.shortcuts import render

def index(request):
    return render(request, 'web/index.html')


# 调用qa_service下的方法，获取答案
def view_get_answer(request):
    question = request.GET.get("question")
    result = get_answer(question)
    return   HttpResponse(result)