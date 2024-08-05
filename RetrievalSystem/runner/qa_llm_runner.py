#encoding:utf-8


import requests
import json
import threading
import sys
import argparse

from .utils import clear_spe_tokens

CONVSATION_START = "<|im_start|>"
CONVSATION_END = "<|im_end|>"
system_info_summary_0 = '''请扮演一个文章摘要总结小助手。请详细了解上面检索到的知识，针对用户的提问给出回答。回答时不允许添加编造虚假内容，做到准确，精炼，与原文内容相符。回答可以以“基于文章内容”作为开始。\n
注意： \n
1. 如果问题与文章无关，需要返回“无法在文章中找到答案” \n
2. 当问题与文献有一定的关系但是又无法在文献中找到直接答案的场景下，可以根据自身知识对问题进行回答 \n
3. 回答时减少引用数字和公式 \n
4. 避免英文专有名词的翻译 \n
5. 回答的语种需要与问题的语种保持一致 \n
现在开始作答： \n
'''
system_info_summary = '''请阅读以下文章，并为其生成一个简明扼要的总结。请确保总结涵盖文章的主要观点和关键信息，并且不超过300字。

文章内容：
{}
'''


system_info_qa = '''请扮演一个文章小助手。需支持针对文档的内容进行问答，答案需来源于文档中。当用户问题与文档不相关或搜索不到对应答案时，回复“抱歉，您所输入的问题在该文档中没有查询到，是否切换云侧模型
处理”\n<文章内容>：\n{}\n<用户问题>：{} 
'''
# TODO
meta_instruction = '''你是由商汤科技研发的人工智能助手，名字是“商量”，英文名是'SenseChat'。当用户和你聊天时，你总是可以提供有帮助的、诚实的、无害的回复。'''
default_parameters = {
    "temperature": 0.3,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1.02,
    "max_new_tokens": 4096,
    "do_sample": False,
}
headers = {"Content-Type": "application/json"}
meta_instruction = '''你是由商汤科技研发的人工智能助手，名字是“商量”，英文名是'SenseChat'。当用户和你聊天时，你总是可以提供有帮助的、诚实的、无害的回复。'''


class RAG_Interenlm2Model:
    def __init__(self, api, parameters=default_parameters):
        self.url = f"{api}/generate"
        print(self.url)
        self.parameters = parameters  # default_parameters_Gauss_20B`

    def chat(self, query, system_info="", history=""):
        system_info = system_info.replace("<system>: ", "")
        system_text = f"<|im_start|><system>: {system_info}\n"
        conv_text = f"<|im_start|><user>: {query}\n"

        input_text = system_text
        input_text += history + conv_text + f"<|im_start|><assistant>: "
        history += conv_text + f"<|im_start|><assistant>: "

        input_data = {"inputs": input_text, "parameters": self.parameters}

        response = requests.post(self.url, headers=headers, json=input_data, stream=True)
        response = response.json()
        response = response["generated_text"][0]

        response = response.replace("<|im_end|>", "")
        history += response + CONVSATION_END + "\n"
        return response, history



class Internlm2:
    def __init__(self, api, parameters):
        self.url = f"{api}/generate"
        self.parameters = parameters
    
    
    def parse_intern_function(self, response):
        interpreter_left = response.find(f"{CODE_INTERPRETER}")
        tool_left = response.find(f"{TOOLS_DEFINE}")
        right = response.find(f"{PLUGIN_END}")

        reses = []
        if ((interpreter_left == -1) and (tool_left == -1)) or right == -1 or ((interpreter_left != -1) and (tool_left != -1)):
            return response

        if (interpreter_left == -1):
            left = tool_left
        else:
            left = interpreter_left
        
        if left >= right:
            return response

        if (interpreter_left == -1):
            tool_str = response[left + len(TOOLS_DEFINE):right]
            calls = tool_str.split(TOOLS_DEFINE)
            for call in calls:
                call = call.strip()
                try:
                    call = json.loads(call)
                    if "parameters" in call:
                        call["arguments"] = call["parameters"]
                    reses.append(call)
                except:
                    pass
            if len(reses) == 0:
                return response
        else:
            calls = response[left+len(CODE_INTERPRETER):right]
            calls = calls.strip()
            try:
                assert (calls.strip()[:10] == "```python\n") and (calls.strip()[-4:] == "\n```")
                code_calls = {'name': 'python_interpreter', 'arguments': {'code': calls}}
                reses.append(code_calls)
            except:
                return response
        return reses     
    
    def chat(self, query, tools=[], system_info="", interpreter=[], history=""):
        
        system_info = system_info.replace("<system>: ", "")
        system_text = f"{CONVSATION_START}system\n{system_info}{CONVSATION_END}\n"
        if interpreter:
            assert (len(interpreter) == 1) and (interpreter[0]["name"] == "python_interpreter"), "Only support python interpreter now!"     # noqa
            interpreter_test = f"{CONVSATION_START}system name={CODE_INTERPRETER}\n{interpreter[0]['description']}\n{CONVSATION_END}\n"
        else:
            interpreter_test = ""
        pure_tools = []
        for tool in tools:
            if tool['function']['name'] != "python_interpreter":
                pure_tools.append(tool['function'])
        if pure_tools:
            tool_text_str = json.dumps(pure_tools, ensure_ascii=False)
            tool_text = f"{CONVSATION_START}system name={TOOLS_DEFINE}\n{tool_text_str}\n{CONVSATION_END}\n"
        else:
            tool_text = ""
        conv_text = f"{CONVSATION_START}user\n{query}{CONVSATION_END}\n"

        input_text = system_text + interpreter_test + tool_text
        input_text += history + conv_text + f"{CONVSATION_START}assistant\n"
        history += conv_text + f"{CONVSATION_START}assistant\n"

        input_data = {
            "inputs": input_text,
            "parameters": self.parameters
        }
        
        response = requests.post(self.url, headers=headers, json=input_data, stream=True)
        response = response.json()
        response = response['generated_text'][0]

        reses = self.parse_intern_function(response)

        #一律转str,不用就注释掉
        reses = str(reses)


        # 文本回答，直接返回
        if isinstance(reses, str):
            reses = reses.replace(" <|im_end|>", "")
            history += reses + CONVSATION_END + "\n"
            return reses, history 
        
        # 拼调用
        input_text1 = input_text + PLUGIN_START
        history = history + PLUGIN_START
        for res in reses:
            tool_name = res['name']
            if interpreter and tool_name == "python_interpreter":
                input_text1 += CODE_INTERPRETER + "\n" + str(res['arguments']['code']) 
                history += CODE_INTERPRETER + "\n" + str(res['arguments']['code']) 
                input_text1 += PLUGIN_END + "\n" + CONVSATION_END + "\n"
                history += PLUGIN_END + "\n" + CONVSATION_END + "\n"
            else:
                input_text1 +=  TOOLS_DEFINE + "\n" + json.dumps(res, ensure_ascii=False) 
                history += TOOLS_DEFINE + "\n" + json.dumps(res, ensure_ascii=False) 
                input_text1 += PLUGIN_END + CONVSATION_END + "\n"
                history += PLUGIN_END + CONVSATION_END + "\n"
        
        # 有调用，调用函数、这里用一个假的结果
        tool_call_results = []
        for res in reses:
            name = res['name']
            kwargs = res['arguments']
            func_res_text = globals().get(name, lambda **_: "'error': f'no such tool {name}'")(**kwargs)
            if not isinstance(func_res_text, str):
                func_res_text = str(func_res_text)
            tool_call_results.append(func_res_text)
        
        # 拼调用结果
        for idx, res in enumerate(reses):
            if interpreter and tool_name == "python_interpreter":
                input_text1 += INTERPRETER_RESULT + "\n" + tool_call_results[idx] + "\n" + CONVSATION_END + "\n"
                history += INTERPRETER_RESULT + "\n" + tool_call_results[idx] + "\n" + CONVSATION_END + "\n"
                
                input_text1 += CONVSATION_START + "assistant\n"
                history += CONVSATION_START + "assistant\n"
                
            else:
                input_text1 += TOOLS_RESULT + "\n" + tool_call_results[idx] + CONVSATION_END + "\n"
                history += TOOLS_RESULT + "\n" + tool_call_results[idx] + CONVSATION_END + "\n"

                input_text1 += CONVSATION_START + "assistant\n"
                history += CONVSATION_START + "assistant\n"
                
        input_data1 = {
            "inputs": input_text1,
            "parameters": self.parameters
        }
        
        response1 = requests.post(self.url, headers=headers, json=input_data1, stream=True)
        response1 = response1.json()
        response1 = response1['generated_text'][0]
        
        res1 = self.parse_intern_function(response1)
        
        
        # 文本总结
        if isinstance(res1, str):
            res1 = res1.replace(" <|im_end|>", "")
            history += res1 + CONVSATION_END + "\n"
            return res1, history
        
        return res1, history



def rag_call(api, args):
    model = RAG_Interenlm2Model(f"{api}")
    if args.mode == 'summary':
        system_info = system_info_summary
    elif args.mode == 'qa':
        system_info = system_info_qa
    if args.generate_mode == "interactive":
        count = 0
        while True:
            print("请输入文档, 退出请输入 quit, 清除历史对话请输入 clean。\n")
            query = input()
            if count == 0:
                history = ""
            if len(query.strip()) == 0:
                break
            if query == "quit":
                break
            if query == "clean":
                history = ""
                continue

            response, history = model.chat(query=query, system_info=system_info, history=history)
            # print("<user>: ", query)
            print(f"\n[count]{count}")
            print("<assistant>: ", response)
            print("\n")
            count += 1

    elif args.generate_mode == "json":
        datas = []
        print("loading..., ", args.json_file, "\n")
        with open(args.json_file) as f:
            for line in f.readlines():
                datas.append(json.loads(line))
        ress = []
        for data in datas:
            res = []
            history = ""
            for item in data:
                if item["role"] == "user":
                    query = item["content"]
                    print("<user>: ", query, '\n')
                    res.append({"role": "user", "content": query})

                    response, history = model.chat(query=query, system_info=system_info, history=history)
                    print("<assistant>: ", response, '\n')
                    res.append({"role": "assistant", "content": response})
            ress.append(res)
        with open((args.json_file).replace(".json", "_response.json"), "w") as f:
            for i in ress:
                print(json.dumps(i, ensure_ascii=False), file=f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", help="summary/qa", default='summary')
    parser.add_argument("--generate_mode", help="interactive/json load", default="interactive")
    parser.add_argument("--json_file")
    args = parser.parse_args()
    if args.mode == "summary":
        rag_call("http://101.230.144.204:80002", args)
    if args.mode == "qa":
        rag_call("http://**.**:2222", args)  # TODO


demo_text = "早上好，我是西部证券的副所长郑宏达。\
人工智能是今年我们非常重点推荐的一个方向，我认为这是一个\n五年的长周期，而我们才刚刚开始了两三个月。同时，商汤作为中国目前做得最好的端侧大模型公司，\
一\n直在积极推进本身的业务。商汤上周发布了去年的年报，我们清晰地看到整个收入结构发生了非常好的变\n化。之前的智慧城市等业务下降比例非常明显，但是许多新兴业务，包括汽车、端侧大模型、AGI 等业务\n保持了非常快速的增长。可以说，商汤迎来了一个崭新的收入结构和一个新的未来。同时，我们也对端侧\n非常看好，我们认为今年将是端侧人工智能大模型的新元年，大模型将实现本地化，装入手机、PC 和汽车\n中。我们也看到商汤在这方面做得非常好。今天，我们非常荣幸邀请到商汤的联合创始人徐冰先生，与大\n家分享和交流。 \n \n徐冰：大家好，我是商汤的联合创始人徐冰。\n今天很高兴有机会介绍我们今年的发展情况，并探讨端侧 AI 的话题。端侧 AI 是我们非常看重的一个领域。\n在去年，我们主要的工作是加强算力的规模、加强模型的能力、把我们的模型部署到各个场景。其中，在\n手机和汽车这两个端侧，我们都做了很多工作。前几天看到的小米 SU7 的发布，里面连接了小爱同学，背\n后就使用了商汤的模型。在手机端，我们判断 AI 手机将成为众多国内手机厂商研发的重点方向。AI 手机\n的核心在于模型对手机中各种 APP 的使用能力。这种能力基于模型的推理和工具调用能力的加强，并实现\n了极致的小型化。在手机芯片端，能够在本地离线进行快速的实时处理。这些能力都具有较高的技术壁垒。 \n \n我们可以想象一个端侧 AI 的简单场景：在我介绍之前，我划了手机屏幕四次，点击进入了进门财经 APP，\n再点击四五次找到参会入口，然后开麦发言。整个过程至少需要十次操作，花费大约五秒。这样一个场景\n是大模型在手机端可以完整复现的。只需一个指令，例如“我要参加路演会”，它便能根据我的日程精准\n识别并调用相应 APP，通过几步 API 调用找到演讲界面。整个过程需在五秒内完成，大约十步操作。这对\n大模型的终端离线使用来说是一个绝佳的场景。未来，我们在手机上使用各种 APP 完成任务，都将依赖于\n智能大模型与手机的紧密结合。我们不再需要用手指戳划手机屏幕，而是通过自然语言让手机成为智能秘\n书，理解我们的喜好和习惯，快速完成离线处理——云端处理难以实现这些任务，且涉及隐私保护问题，\n手机中存储的个人隐私数据不宜大规模上传至云端。因此，AI 手机的终端离线强化大模型工具使用能力将\n释放巨大潜力。我很期待与大家探讨如何实现这一目标，以及我们目前的发展阶段。今年我们能否看到这\n样的应用，新款手机能否实现这些功能并成为新的爆款？\n\n"




def call_intern_qa(query, ref_text):
    
    API = "http://101.230.144.204:16004"
    parameters = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1.02,
    "max_new_tokens": 1024,
    "do_sample": True,
    }

    model = RAG_Interenlm2Model(f'{API}', parameters=parameters)

    # print(system_info_summary.format(query))
    print(system_info_qa.format(ref_text, query))
    response, history = model.chat(query=system_info_qa.format(ref_text, query), system_info=meta_instruction, history="")

    return clear_spe_tokens(response)


# import debugpy

# debugpy.connect(("10.119.169.141", 5678))
if __name__ == "__main__":
    # main()
    demo_text = "早上好，我是西部证券的副所长郑宏达。人工智能是今年我们非常重点推荐的一个方向，我认为这是一个\n五年的长周期，而我们才刚刚开始了两三个月。同时，商汤作为中国目前做得最好的端侧大模型公司，一\n直在积极推进本身的业务。商汤上周发布了去年的年报，我们清晰地看到整个收入结构发生了非常好的变\n化。之前的智慧城市等业务下降比例非常明显，但是许多新兴业务，包括汽车、端侧大模型、AGI 等业务\n保持了非常快速的增长。可以说，商汤迎来了一个崭新的收入结构和一个新的未来。同时，我们也对端侧\n非常看好，我们认为今年将是端侧人工智能大模型的新元年，大模型将实现本地化，装入手机、PC 和汽车\n中。我们也看到商汤在这方面做得非常好。今天，我们非常荣幸邀请到商汤的联合创始人徐冰先生，与大\n家分享和交流。 \n \n徐冰：大家好，我是商汤的联合创始人徐冰。\n今天很高兴有机会介绍我们今年的发展情况，并探讨端侧 AI 的话题。端侧 AI 是我们非常看重的一个领域。\n在去年，我们主要的工作是加强算力的规模、加强模型的能力、把我们的模型部署到各个场景。其中，在\n手机和汽车这两个端侧，我们都做了很多工作。前几天看到的小米 SU7 的发布，里面连接了小爱同学，背\n后就使用了商汤的模型。在手机端，我们判断 AI 手机将成为众多国内手机厂商研发的重点方向。AI 手机\n的核心在于模型对手机中各种 APP 的使用能力。这种能力基于模型的推理和工具调用能力的加强，并实现\n了极致的小型化。在手机芯片端，能够在本地离线进行快速的实时处理。这些能力都具有较高的技术壁垒。 \n \n我们可以想象一个端侧 AI 的简单场景：在我介绍之前，我划了手机屏幕四次，点击进入了进门财经 APP，\n再点击四五次找到参会入口，然后开麦发言。整个过程至少需要十次操作，花费大约五秒。这样一个场景\n是大模型在手机端可以完整复现的。只需一个指令，例如“我要参加路演会”，它便能根据我的日程精准\n识别并调用相应 APP，通过几步 API 调用找到演讲界面。整个过程需在五秒内完成，大约十步操作。这对\n大模型的终端离线使用来说是一个绝佳的场景。未来，我们在手机上使用各种 APP 完成任务，都将依赖于\n智能大模型与手机的紧密结合。我们不再需要用手指戳划手机屏幕，而是通过自然语言让手机成为智能秘\n书，理解我们的喜好和习惯，快速完成离线处理——云端处理难以实现这些任务，且涉及隐私保护问题，\n手机中存储的个人隐私数据不宜大规模上传至云端。因此，AI 手机的终端离线强化大模型工具使用能力将\n释放巨大潜力。我很期待与大家探讨如何实现这一目标，以及我们目前的发展阶段。今年我们能否看到这\n样的应用，新款手机能否实现这些功能并成为新的爆款？\n\n"
    demo_question = "徐冰是谁？"
    response = call_intern_qa(demo_question, demo_text)

    print(response)